import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SKILL_FILE = BASE_DIR / "fxalex_skill_v2.json"
DECISION_SCHEMA_FILE = BASE_DIR / "fxalex_decision_schema.json"
LIVE_SNAPSHOT_FILE = BASE_DIR / "live_snapshot.json"
CLAIMS_FILE = Path("/Users/jeroenderaaf/alexbecker_dump/fxalexg/processed/fxalex_claims_v3.jsonl")


BULLISH_HINTS = [
    "bullish",
    "higher high",
    "higher low",
    "support",
    "resistance flip to support",
    "buy",
    "long",
    "confirmation",
    "breakout",
    "retest"
]

BEARISH_HINTS = [
    "bearish",
    "lower high",
    "lower low",
    "resistance",
    "support flip to resistance",
    "sell",
    "short",
    "confirmation",
    "breakdown",
    "retest"
]

RISK_HINTS = [
    "risk reward",
    "1 to 2",
    "1 to 3",
    "stop loss",
    "take profit",
    "risk",
    "position size",
    "lot size"
]

MANAGEMENT_HINTS = [
    "set and forget",
    "leave the trade",
    "let it run",
    "close the trade",
    "manage the trade",
    "breakeven"
]


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_claims(path: Path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def unique_in_order(items):
    seen = set()
    ordered = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def matches_type(value, expected_type):
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def validate_snapshot(snapshot: dict, schema: dict):
    errors = []

    for field in schema["fields"]:
        name = field["name"]

        if field.get("required") and name not in snapshot:
            errors.append(f"Missing required field: {name}")
            continue

        if name not in snapshot:
            continue

        value = snapshot[name]
        if value is None and not field.get("required"):
            continue

        if not matches_type(value, field["type"]):
            errors.append(f"Field {name} must be of type {field['type']}.")
            continue

        allowed_values = field.get("allowed_values")
        if allowed_values and value not in allowed_values:
            errors.append(f"Field {name} has invalid value {value!r}.")

        field_range = field.get("range")
        if field_range and matches_type(value, "number"):
            lower, upper = field_range
            if value < lower or value > upper:
                errors.append(f"Field {name} must be between {lower} and {upper}.")

    return errors


def validate_reason_codes(reason_codes: list, schema: dict):
    known_codes = set(schema.get("reason_code_catalog", []))
    return [code for code in reason_codes if code not in known_codes]


def serialize_top_claims(top_claims: list, limit: int = 5):
    serialized = []
    for item in top_claims[:limit]:
        serialized.append({
            "score": item["score"],
            "tags": item["tags"],
            "claim_text": item["claim_text"],
            "video_id": item["video_id"],
            "title": item["title"],
            "categories": item["categories"],
        })
    return serialized


def build_error_payload(snapshot: dict, mode_used: str, error_code: str, summary: str, errors: list):
    return {
        "decision": "WAIT",
        "confidence_score": 0,
        "reason_codes": [error_code],
        "summary": summary,
        "mode_used": mode_used,
        "advisory_mode": True,
        "execution_allowed": False,
        "pair": snapshot.get("pair", "UNKNOWN"),
        "timeframe": snapshot.get("timeframe", "UNKNOWN"),
        "validation": {
            "ok": False,
            "errors": errors,
        },
    }


def build_advisory_payload(snapshot: dict, rule_result: dict, vote_result: dict, vote_eval: dict, hybrid: dict):
    return {
        "decision": hybrid["decision"],
        "confidence_score": hybrid["confidence_score"],
        "reason_codes": unique_in_order(hybrid["reason_codes"]),
        "summary": hybrid["summary"],
        "mode_used": rule_result["mode_used"],
        "advisory_mode": True,
        "execution_allowed": False,
        "pair": snapshot["pair"],
        "timeframe": snapshot["timeframe"],
        "validation": {
            "ok": True,
            "errors": [],
        },
        "layers": {
            "rule_engine": {
                "decision": rule_result["decision"],
                "confidence_score": rule_result["confidence_score"],
                "reason_codes": unique_in_order(rule_result["reason_codes"]),
                "summary": rule_result["summary"],
                "gate_blocked": rule_result.get("gate_blocked", False),
            },
            "claims_voting": {
                "decision": vote_eval["decision"],
                "confidence_score": vote_eval["confidence_score"],
                "vote_direction": vote_result["direction"],
                "vote_score": vote_result["total_score"],
                "summary": vote_eval["summary"],
                "top_claims": serialize_top_claims(vote_result["top_claims"]),
            },
        },
    }


def render_text_report(payload: dict):
    lines = [
        "=" * 100,
        "LIVE SNAPSHOT RESULT",
        f"Pair: {payload['pair']} | Timeframe: {payload['timeframe']} | Mode: {payload['mode_used']}",
        "",
    ]

    if not payload["validation"]["ok"]:
        lines.extend([
            "VALIDATION FAILED",
            f"Decision:       {payload['decision']} | confidence={payload['confidence_score']}",
            f"Reason codes:   {payload['reason_codes']}",
            f"Summary:        {payload['summary']}",
            "Errors:",
        ])
        for error in payload["validation"]["errors"]:
            lines.append(f"  - {error}")
        return "\n".join(lines)

    rule_layer = payload["layers"]["rule_engine"]
    vote_layer = payload["layers"]["claims_voting"]
    lines.extend([
        f"RULE decision:   {rule_layer['decision']} | confidence={rule_layer['confidence_score']}",
        f"VOTE decision:   {vote_layer['decision']} | confidence={vote_layer['confidence_score']} | vote_score={vote_layer['vote_score']}",
        f"FINAL decision:  {payload['decision']} | confidence={payload['confidence_score']}",
        f"Reason codes:    {payload['reason_codes']}",
        f"Summary:         {payload['summary']}",
        "Top claims:",
    ])

    for item in vote_layer["top_claims"]:
        lines.append(f"  - score={item['score']} | tags={item['tags']} | text={item['claim_text'][:180]}")

    return "\n".join(lines)


def emit_payload(payload: dict, output_format: str):
    if output_format == "text":
        print(render_text_report(payload))
        return

    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    print()


# -----------------------------
# RULE ENGINE
# -----------------------------
def evaluate_rules(example, skill):
    mode = example["mode"]
    mode_config = skill["modes"][mode]

    reason_codes = []
    notes = []

    if example["bias"] in ["neutral", "unknown"]:
        return {
            "decision": "WAIT",
            "confidence_score": 35,
            "reason_codes": ["BIAS_UNKNOWN"],
            "summary": "Geen duidelijke bias, dus wachten.",
            "mode_used": mode,
            "gate_blocked": True
        }

    if example["market_structure_state"] in ["range", "unclear"]:
        return {
            "decision": "WAIT",
            "confidence_score": 35,
            "reason_codes": ["STRUCTURE_UNCLEAR"],
            "summary": "Market structure is niet duidelijk.",
            "mode_used": mode,
            "gate_blocked": True
        }

    if example["confirmation_present"] is False:
        return {
            "decision": "WAIT",
            "confidence_score": 30,
            "reason_codes": ["CONFIRMATION_MISSING"],
            "summary": "Confirmation ontbreekt.",
            "mode_used": mode,
            "gate_blocked": True
        }

    if example["risk_reward_ratio"] < mode_config["min_risk_reward"]:
        return {
            "decision": "NO-GO",
            "confidence_score": 25,
            "reason_codes": ["RR_TOO_LOW"],
            "summary": "Risk/Reward onder minimum.",
            "mode_used": mode,
            "gate_blocked": True
        }

    if example["planned_risk_percent"] > mode_config["max_risk_percent"]:
        return {
            "decision": "NO-GO",
            "confidence_score": 25,
            "reason_codes": ["RISK_TOO_HIGH"],
            "summary": "Gepland risico te hoog.",
            "mode_used": mode,
            "gate_blocked": True
        }

    if example["setup_quality"] < mode_config["min_setup_quality"]:
        return {
            "decision": "WAIT",
            "confidence_score": 40,
            "reason_codes": ["SETUP_TOO_WEAK"],
            "summary": "Setupkwaliteit te laag.",
            "mode_used": mode,
            "gate_blocked": True
        }

    if example["set_and_forget_possible"] is False:
        return {
            "decision": "WAIT",
            "confidence_score": 40,
            "reason_codes": ["SET_AND_FORGET_NOT_POSSIBLE"],
            "summary": "Set & Forget niet mogelijk.",
            "mode_used": mode,
            "gate_blocked": True
        }

    if example["trader_condition"] in ["tired", "traveling", "distracted"]:
        return {
            "decision": "WAIT",
            "confidence_score": 35,
            "reason_codes": ["TRADER_STATE_BAD"],
            "summary": "Trader conditie niet goed.",
            "mode_used": mode,
            "gate_blocked": True
        }

    decision = "WAIT"
    confidence = 70

    if (
        example["bias"] == "bullish"
        and example["market_structure_state"] == "bullish_confirmed"
        and example["confirmation_present"]
    ):
        decision = "BUY"
        reason_codes.extend([
            "BIAS_CONFIRMED",
            "STRUCTURE_CONFIRMED",
            "CONFIRMATION_PRESENT",
            "RR_VALID"
        ])
        notes.append("Bullish bias + structure + confirmation.")

    elif (
        example["bias"] == "bearish"
        and example["market_structure_state"] == "bearish_confirmed"
        and example["confirmation_present"]
    ):
        decision = "SELL"
        reason_codes.extend([
            "BIAS_CONFIRMED",
            "STRUCTURE_CONFIRMED",
            "CONFIRMATION_PRESENT",
            "RR_VALID"
        ])
        notes.append("Bearish bias + structure + confirmation.")

    else:
        return {
            "decision": "WAIT",
            "confidence_score": 45,
            "reason_codes": ["MODE_MISMATCH"],
            "summary": "Context onvoldoende voor directionele trade.",
            "mode_used": mode,
            "gate_blocked": False
        }

    if example["support_resistance_context"] in ["resistance_flip_to_support", "support_holding"] and decision == "BUY":
        confidence += 8
        reason_codes.append("SR_CONFIRMS_BUY")
        notes.append("Support/Resistance bevestigt BUY.")

    if example["support_resistance_context"] in ["support_flip_to_resistance", "resistance_holding"] and decision == "SELL":
        confidence += 8
        reason_codes.append("SR_CONFIRMS_SELL")
        notes.append("Support/Resistance bevestigt SELL.")

    if example["ema_context"] == "bullish_support" and decision == "BUY":
        confidence += 5
        reason_codes.append("EMA_SUPPORTS")
        notes.append("EMA ondersteunt BUY.")

    if example["ema_context"] == "bearish_resistance" and decision == "SELL":
        confidence += 5
        reason_codes.append("EMA_SUPPORTS")
        notes.append("EMA ondersteunt SELL.")

    if example["liquidity_context"] in ["sweep_present", "liquidity_taken"]:
        confidence += 5
        reason_codes.append("LIQUIDITY_CONFIRMS")
        notes.append("Liquidity sweep aanwezig.")

    if example["setup_quality"] >= 9:
        confidence += 7
        reason_codes.append("SETUP_STRONG")
        notes.append("Zeer sterke setup.")

    confidence = min(confidence, 100)

    return {
        "decision": decision,
        "confidence_score": confidence,
        "reason_codes": reason_codes,
        "summary": " | ".join(notes),
        "mode_used": mode,
        "gate_blocked": False
    }


# -----------------------------
# CLAIMS VOTER
# -----------------------------
def score_claim_text(text: str, example: dict):
    text_lower = text.lower()
    score = 0
    tags = []

    if example["bias"] == "bullish":
        if any(h in text_lower for h in BULLISH_HINTS):
            score += 2
            tags.append("BULLISH_CLAIM_MATCH")
        if any(h in text_lower for h in BEARISH_HINTS):
            score -= 1
            tags.append("BEARISH_CONFLICT")

    if example["bias"] == "bearish":
        if any(h in text_lower for h in BEARISH_HINTS):
            score += 2
            tags.append("BEARISH_CLAIM_MATCH")
        if any(h in text_lower for h in BULLISH_HINTS):
            score -= 1
            tags.append("BULLISH_CONFLICT")

    if example["market_structure_state"] == "bullish_confirmed":
        if "bullish" in text_lower or "higher high" in text_lower or "higher low" in text_lower:
            score += 2
            tags.append("STRUCTURE_SUPPORTS")

    elif example["market_structure_state"] == "bearish_confirmed":
        if "bearish" in text_lower or "lower high" in text_lower or "lower low" in text_lower:
            score += 2
            tags.append("STRUCTURE_SUPPORTS")

    if example["confirmation_present"] and "confirmation" in text_lower:
        score += 1
        tags.append("CONFIRMATION_SUPPORTS")

    if any(h in text_lower for h in RISK_HINTS):
        if example["risk_reward_ratio"] >= 2.0:
            score += 1
            tags.append("RISK_FRAME_SUPPORTS")
        else:
            score -= 1
            tags.append("RISK_FRAME_CONFLICTS")

    if example["set_and_forget_possible"] and any(h in text_lower for h in MANAGEMENT_HINTS):
        score += 1
        tags.append("MANAGEMENT_SUPPORTS")

    return score, tags


def vote_claims(example: dict, claims: list, top_n: int = 30):
    scored = []

    for claim in claims:
        text = claim.get("claim_text", "")
        score, tags = score_claim_text(text, example)

        if score != 0:
            scored.append({
                "score": score,
                "tags": tags,
                "claim_text": text,
                "video_id": claim.get("video_id"),
                "title": claim.get("title"),
                "categories": claim.get("categories", [])
            })

    scored.sort(key=lambda x: x["score"], reverse=True)

    top = scored[:top_n]
    total_score = sum(x["score"] for x in top)

    direction = "NEUTRAL"
    if total_score >= 20:
        direction = "STRONG_SUPPORT"
    elif total_score >= 8:
        direction = "SUPPORT"
    elif total_score <= -8:
        direction = "CONFLICT"

    return {
        "total_score": total_score,
        "direction": direction,
        "top_claims": top[:10]
    }


def evaluate_vote_only(example: dict, vote_result: dict):
    direction = vote_result["direction"]
    total_score = vote_result["total_score"]

    if not example["confirmation_present"]:
        return {
            "decision": "WAIT",
            "confidence_score": 30,
            "summary": "Claims kunnen confirmation niet vervangen.",
            "vote_score": total_score
        }

    if example["risk_reward_ratio"] < 2.0:
        return {
            "decision": "NO-GO",
            "confidence_score": 25,
            "summary": "Claims kunnen een slechte RR niet redden.",
            "vote_score": total_score
        }

    if example["bias"] == "bullish" and example["market_structure_state"] == "bullish_confirmed":
        if direction in ["SUPPORT", "STRONG_SUPPORT"]:
            return {
                "decision": "BUY",
                "confidence_score": min(60 + total_score, 95),
                "summary": "Claims ondersteunen bullish setup.",
                "vote_score": total_score
            }

    if example["bias"] == "bearish" and example["market_structure_state"] == "bearish_confirmed":
        if direction in ["SUPPORT", "STRONG_SUPPORT"]:
            return {
                "decision": "SELL",
                "confidence_score": min(60 + total_score, 95),
                "summary": "Claims ondersteunen bearish setup.",
                "vote_score": total_score
            }

    return {
        "decision": "WAIT",
        "confidence_score": max(35, min(60, 50 + total_score)),
        "summary": "Claims geven onvoldoende steun.",
        "vote_score": total_score
    }


# -----------------------------
# HYBRID DECISION
# -----------------------------
def combine_decisions(rule_result: dict, vote_result: dict, vote_eval: dict):
    final_decision = rule_result["decision"]
    final_confidence = rule_result["confidence_score"]
    final_reason_codes = list(rule_result["reason_codes"])
    hybrid_notes = [f"Rule engine: {rule_result['summary']}"]

    if rule_result.get("gate_blocked", False):
        hybrid_notes.append("Hard gate actief, claims vote wordt niet leidend.")
        return {
            "decision": final_decision,
            "confidence_score": final_confidence,
            "reason_codes": unique_in_order(final_reason_codes + ["RULE_ENGINE_HARD_GATE"]),
            "summary": " | ".join(hybrid_notes),
            "top_claims": vote_result["top_claims"]
        }

    if rule_result["decision"] == vote_eval["decision"] and rule_result["decision"] in ["BUY", "SELL"]:
        bonus = 0
        if vote_result["direction"] == "STRONG_SUPPORT":
            bonus = 8
            final_reason_codes.append("CLAIMS_STRONG_SUPPORT")
        elif vote_result["direction"] == "SUPPORT":
            bonus = 4
            final_reason_codes.append("CLAIMS_SUPPORT")

        final_confidence = min(100, final_confidence + bonus)
        hybrid_notes.append(f"Claims vote bevestigt {rule_result['decision']} met score {vote_result['total_score']}.")

    elif rule_result["decision"] in ["BUY", "SELL"] and vote_result["direction"] == "CONFLICT":
        final_decision = "WAIT"
        final_confidence = max(35, rule_result["confidence_score"] - 20)
        final_reason_codes.append("CLAIMS_CONFLICT")
        hybrid_notes.append(f"Claims vote conflicteert met {rule_result['decision']} (score {vote_result['total_score']}). Downgrade naar WAIT.")

    elif rule_result["decision"] in ["BUY", "SELL"] and vote_result["direction"] == "NEUTRAL":
        final_confidence = max(45, rule_result["confidence_score"] - 8)
        final_reason_codes.append("CLAIMS_NEUTRAL")
        hybrid_notes.append("Claims vote is neutraal, dus confidence iets lager.")

    elif rule_result["decision"] == "WAIT" and vote_result["direction"] in ["SUPPORT", "STRONG_SUPPORT"]:
        final_reason_codes.append("CLAIMS_SUPPORT_BUT_RULE_WAIT")
        hybrid_notes.append("Claims zijn positief, maar rule engine blijft leidend en houdt WAIT aan.")

    return {
        "decision": final_decision,
        "confidence_score": final_confidence,
        "reason_codes": unique_in_order(final_reason_codes),
        "summary": " | ".join(hybrid_notes),
        "top_claims": vote_result["top_claims"]
    }


def main():
    parser = argparse.ArgumentParser(description="Run the fxalex hybrid advisory engine.")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--skill-file", type=Path, default=SKILL_FILE)
    parser.add_argument("--schema-file", type=Path, default=DECISION_SCHEMA_FILE)
    parser.add_argument("--snapshot-file", type=Path, default=LIVE_SNAPSHOT_FILE)
    parser.add_argument("--claims-file", type=Path, default=CLAIMS_FILE)
    args = parser.parse_args()

    skill = load_json(args.skill_file)
    schema = load_json(args.schema_file)
    snapshot = load_json(args.snapshot_file)

    snapshot_errors = validate_snapshot(snapshot, schema)
    if snapshot_errors:
        payload = build_error_payload(
            snapshot=snapshot,
            mode_used=snapshot.get("mode", "unknown"),
            error_code="INPUT_SCHEMA_INVALID",
            summary="Snapshot validatie tegen het decision schema is mislukt.",
            errors=snapshot_errors,
        )
        emit_payload(payload, args.format)
        return 1

    claims = load_claims(args.claims_file)

    rule_result = evaluate_rules(snapshot, skill)
    vote_result = vote_claims(snapshot, claims, top_n=30)
    vote_eval = evaluate_vote_only(snapshot, vote_result)
    hybrid = combine_decisions(rule_result, vote_result, vote_eval)

    unknown_reason_codes = validate_reason_codes(hybrid["reason_codes"], schema)
    if unknown_reason_codes:
        payload = build_error_payload(
            snapshot=snapshot,
            mode_used=rule_result["mode_used"],
            error_code="OUTPUT_SCHEMA_INVALID",
            summary="Finale reason codes staan niet in het decision schema.",
            errors=[f"Unknown reason code: {code}" for code in unknown_reason_codes],
        )
        emit_payload(payload, args.format)
        return 1

    payload = build_advisory_payload(snapshot, rule_result, vote_result, vote_eval, hybrid)
    emit_payload(payload, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
