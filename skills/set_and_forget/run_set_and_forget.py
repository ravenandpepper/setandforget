import argparse
import importlib.util
import json
import sys
from pathlib import Path
import news_context
import paper_trading

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = BASE_DIR.parent.parent
FXALEX_RUNNER_FILE = WORKSPACE_ROOT / "skills" / "fxalex" / "run_fxalex_hybrid.py"

SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"
DECISION_SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"
LIVE_SNAPSHOT_FILE = BASE_DIR / "live_snapshot.json"
PAPER_TRADES_LOG_FILE = BASE_DIR / "paper_trades_log.jsonl"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


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

    confluence_count = sum(
        1
        for key in ["aoi_has_sr", "aoi_has_order_block", "aoi_has_structural_level"]
        if snapshot.get(key) is True
    )
    if "aoi_confluence_count" in snapshot and snapshot["aoi_confluence_count"] != confluence_count:
        errors.append("Field aoi_confluence_count must match the AOI confluence booleans.")

    return errors


def validate_reason_codes(reason_codes: list, schema: dict):
    known_codes = set(schema.get("reason_code_catalog", []))
    return [code for code in reason_codes if code not in known_codes]


def load_fxalex_module():
    spec = importlib.util.spec_from_file_location("fxalex_hybrid_module", FXALEX_RUNNER_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_error_payload(snapshot: dict, error_code: str, summary: str, errors: list):
    return {
        "decision": "WAIT",
        "confidence_score": 0,
        "reason_codes": [error_code],
        "summary": summary,
        "primary_strategy": "set_and_forget",
        "execution_mode": snapshot.get("execution_mode", "paper"),
        "pair": snapshot.get("pair", "UNKNOWN"),
        "execution_timeframe": snapshot.get("execution_timeframe", "UNKNOWN"),
        "validation": {
            "ok": False,
            "errors": errors
        },
        "advisory_layers": {
            "fxalex": {
                "enabled": False,
                "used": False,
                "impact": "not_applied"
            }
        }
    }


def build_payload(snapshot: dict, result: dict):
    news_context_state = result["advisory_layers"].get("news_context", {
        "enabled": False,
        "used": False,
        "impact": "not_applied",
        "reason_codes": [],
        "summary": "",
        "should_wait": False,
        "confidence_penalty": 0,
    })

    return {
        "decision": result["decision"],
        "confidence_score": result["confidence_score"],
        "reason_codes": unique_in_order(result["reason_codes"]),
        "summary": result["summary"],
        "primary_strategy": "set_and_forget",
        "execution_mode": snapshot["execution_mode"],
        "pair": snapshot["pair"],
        "execution_timeframe": snapshot["execution_timeframe"],
        "validation": {
            "ok": True,
            "errors": []
        },
        "layers": {
            "primary_rule_engine": {
                "trend_alignment": {
                    "weekly_trend": snapshot["weekly_trend"],
                    "daily_trend": snapshot["daily_trend"]
                },
                "pullback": {
                    "direction": snapshot["h4_pullback_direction"],
                    "structure": snapshot["h4_pullback_structure"],
                    "reversal_state": snapshot["h4_reversal_state"],
                    "break_of_structure": snapshot["h4_break_of_structure"],
                    "first_entry_structure": snapshot["first_entry_structure"]
                },
                "aoi": {
                    "zone_status": snapshot["aoi_zone_status"],
                    "confluence_count": snapshot["aoi_confluence_count"]
                }
            }
        },
        "advisory_layers": {
            "fxalex": result["advisory_layers"]["fxalex"],
            "news_context": news_context_state,
        },
        "paper_trade": {
            "created": False,
            "log_path": str(PAPER_TRADES_LOG_FILE),
            "ticket": None
        },
    }


def expected_pullback(higher_trend: str):
    if higher_trend == "bullish":
        return "bearish", "ll_lh", "confirmed_bullish", "first_hl"
    return "bullish", "hh_hl", "confirmed_bearish", "first_lh"


def evaluate_rules(snapshot: dict, skill: dict):
    weekly_trend = snapshot["weekly_trend"]
    daily_trend = snapshot["daily_trend"]

    if weekly_trend in ["neutral", "unknown"] or daily_trend in ["neutral", "unknown"]:
        return {
            "decision": "WAIT",
            "confidence_score": 30,
            "reason_codes": ["HIGHER_TF_UNCLEAR"],
            "summary": "Weekly en Daily trend zijn niet duidelijk genoeg."
        }

    if weekly_trend != daily_trend:
        return {
            "decision": "WAIT",
            "confidence_score": 28,
            "reason_codes": ["HIGHER_TF_MISALIGNED"],
            "summary": "Weekly en Daily zijn niet aligned, dus geen trade."
        }

    higher_trend = weekly_trend
    pullback_direction, pullback_structure, reversal_state, first_entry = expected_pullback(higher_trend)

    if snapshot["h4_pullback_direction"] != pullback_direction or snapshot["h4_pullback_structure"] != pullback_structure:
        return {
            "decision": "WAIT",
            "confidence_score": 34,
            "reason_codes": ["HIGHER_TF_ALIGNED", "PULLBACK_NOT_PRESENT"],
            "summary": "Hogere trend is duidelijk, maar 4H laat nog niet de juiste tegenbeweging zien."
        }

    if snapshot["h4_reversal_state"] != reversal_state or not snapshot["h4_break_of_structure"]:
        return {
            "decision": "WAIT",
            "confidence_score": 38,
            "reason_codes": ["HIGHER_TF_ALIGNED", "PULLBACK_CONFIRMED", "H4_REVERSAL_NOT_CONFIRMED"],
            "summary": "De 4H pullback is aanwezig, maar de structuurdraai is nog niet bevestigd."
        }

    if snapshot["first_entry_structure"] != first_entry:
        return {
            "decision": "WAIT",
            "confidence_score": 40,
            "reason_codes": ["HIGHER_TF_ALIGNED", "PULLBACK_CONFIRMED", "H4_REVERSAL_CONFIRMED", "FIRST_ENTRY_STRUCTURE_MISSING"],
            "summary": "De 4H draai is zichtbaar, maar de eerste HL/LH entrystructuur is nog niet compleet."
        }

    if snapshot["aoi_zone_status"] != "inside_50_61_8":
        return {
            "decision": "WAIT",
            "confidence_score": 35,
            "reason_codes": ["AOI_NOT_READY"],
            "summary": "Prijs zit nog niet in de 50%-61.8% AOI."
        }

    if snapshot["aoi_confluence_count"] < 3:
        return {
            "decision": "WAIT",
            "confidence_score": 35,
            "reason_codes": ["AOI_CONFLUENCE_TOO_WEAK"],
            "summary": "De AOI heeft minder dan drie confluences."
        }

    if not snapshot["confirmation_present"] or snapshot["confirmation_type"] in ["none", "unknown"]:
        return {
            "decision": "WAIT",
            "confidence_score": 30,
            "reason_codes": ["CONFIRMATION_MISSING"],
            "summary": "Confirmation ontbreekt of candle-close is niet bruikbaar."
        }

    if snapshot["high_impact_news_imminent"]:
        return {
            "decision": "WAIT",
            "confidence_score": 25,
            "reason_codes": ["NEWS_BLOCK"],
            "summary": "High-impact nieuws staat op korte termijn gepland."
        }

    if snapshot["session_window"] != "london_newyork_overlap":
        return {
            "decision": "WAIT",
            "confidence_score": 30,
            "reason_codes": ["SESSION_BLOCK"],
            "summary": "De setup valt buiten de Londen-New York overlap."
        }

    if snapshot["planned_risk_percent"] > skill["risk_policy"]["max_risk_percent"]:
        return {
            "decision": "NO-GO",
            "confidence_score": 20,
            "reason_codes": ["RISK_TOO_HIGH"],
            "summary": "Het geplande risico ligt boven 2%."
        }

    if snapshot["risk_reward_ratio"] < skill["risk_policy"]["min_risk_reward"]:
        return {
            "decision": "NO-GO",
            "confidence_score": 22,
            "reason_codes": ["RR_TOO_LOW"],
            "summary": "De risk/reward is lager dan 1:2."
        }

    if snapshot["open_trades_count"] >= skill["risk_policy"]["max_open_trades"]:
        return {
            "decision": "WAIT",
            "confidence_score": 28,
            "reason_codes": ["OPEN_TRADES_LIMIT_REACHED"],
            "summary": "Er staan al maximaal twee trades open."
        }

    if not snapshot["set_and_forget_possible"]:
        return {
            "decision": "WAIT",
            "confidence_score": 32,
            "reason_codes": ["SET_AND_FORGET_NOT_POSSIBLE"],
            "summary": "De trade is niet uitvoerbaar als set-and-forget."
        }

    if snapshot["stop_loss_basis"] not in ["last_swing", "fib_78_6"]:
        return {
            "decision": "NO-GO",
            "confidence_score": 20,
            "reason_codes": ["STOP_PLACEMENT_INVALID"],
            "summary": "De stop-loss ligt niet achter de laatste swing of de 78.6% retracement."
        }

    decision = "BUY" if higher_trend == "bullish" else "SELL"
    confidence = 72
    reason_codes = [
        "HIGHER_TF_ALIGNED",
        "PULLBACK_CONFIRMED",
        "H4_REVERSAL_CONFIRMED",
        "FIRST_ENTRY_STRUCTURE_READY",
        "AOI_VALID",
        "CONFIRMATION_PRESENT",
        "RR_VALID"
    ]
    notes = [
        f"Weekly en Daily zijn {higher_trend}.",
        "De 4H pullback tegen de hogere trend is aanwezig.",
        "De 4H structuurdraai is bevestigd.",
        f"Entry ligt op de {first_entry.replace('_', ' ')} binnen de AOI."
    ]

    if decision == "BUY":
        reason_codes.append("BULLISH_SWING_READY")
        notes.append("Bullish Set & Forget swing is klaar voor uitvoering in paper mode.")
    else:
        reason_codes.append("BEARISH_SWING_READY")
        notes.append("Bearish Set & Forget swing is klaar voor uitvoering in paper mode.")

    if snapshot["aoi_confluence_count"] >= 4:
        confidence += 6
        reason_codes.append("AOI_CONFLUENCE_STRONG")
        notes.append("De AOI heeft extra confluence.")

    if snapshot["h4_break_of_structure"]:
        confidence += 5
        reason_codes.append("BOS_CONFIRMED")
        notes.append("Break of structure bevestigt de draai.")

    if snapshot["confirmation_type"] in ["bullish_engulfing", "bearish_engulfing"]:
        confidence += 4
        reason_codes.append("ENGULFING_CONFIRMATION")
        notes.append("Engulfing candle geeft sterke bevestiging.")
    elif snapshot["confirmation_type"] == "hammer":
        confidence += 3
        reason_codes.append("HAMMER_CONFIRMATION")
        notes.append("Hammer bevestigt de instapzone.")
    elif snapshot["confirmation_type"] == "shooting_star":
        confidence += 3
        reason_codes.append("SHOOTING_STAR_CONFIRMATION")
        notes.append("Shooting star bevestigt de instapzone.")

    if snapshot["risk_reward_ratio"] >= 2.5:
        confidence += 4
        reason_codes.append("RR_STRONG")
        notes.append("Risk/reward is sterker dan het minimum.")

    if snapshot["open_trades_count"] == 0:
        confidence += 2
        reason_codes.append("PORTFOLIO_CAPACITY_OK")
        notes.append("Er is volledige portfolio-capaciteit beschikbaar.")

    confidence = min(confidence, 95)

    return {
        "decision": decision,
        "confidence_score": confidence,
        "reason_codes": unique_in_order(reason_codes),
        "summary": " | ".join(notes)
    }


def build_fxalex_snapshot(snapshot: dict, primary_result: dict):
    decision = primary_result["decision"]
    bullish = decision == "BUY"

    support_resistance_context = "not_clear"
    if snapshot["aoi_has_sr"]:
        support_resistance_context = "resistance_flip_to_support" if bullish else "support_flip_to_resistance"

    setup_quality = min(
        10,
        6
        + snapshot["aoi_confluence_count"]
        + (1 if snapshot["h4_break_of_structure"] else 0)
        + (1 if snapshot["confirmation_present"] else 0)
    )

    return {
        "pair": snapshot["pair"],
        "timeframe": snapshot["execution_timeframe"],
        "mode": "normal",
        "bias": "bullish" if bullish else "bearish",
        "market_structure_state": "bullish_confirmed" if bullish else "bearish_confirmed",
        "support_resistance_context": support_resistance_context,
        "ema_context": "none",
        "liquidity_context": "unknown",
        "confirmation_present": snapshot["confirmation_present"],
        "setup_quality": setup_quality,
        "entry_price": snapshot.get("entry_price"),
        "stop_loss_price": snapshot.get("stop_loss_price"),
        "take_profit_price": snapshot.get("take_profit_price"),
        "risk_reward_ratio": snapshot["risk_reward_ratio"],
        "planned_risk_percent": snapshot["planned_risk_percent"],
        "set_and_forget_possible": snapshot["set_and_forget_possible"],
        "trader_condition": "unknown",
        "notes": "Derived advisory snapshot from the primary Set & Forget engine."
    }


def maybe_apply_fxalex_confluence(snapshot: dict, primary_result: dict, skill: dict):
    fxalex_config = skill["advisory_layers"]["fxalex"]
    enabled = snapshot.get("fxalex_confluence_enabled", fxalex_config.get("enabled_by_default", False))

    advisory_state = {
        "enabled": enabled,
        "used": False,
        "impact": "not_applied"
    }

    if not enabled:
        result = dict(primary_result)
        result["advisory_layers"] = {"fxalex": advisory_state}
        return result

    if primary_result["decision"] not in ["BUY", "SELL"]:
        advisory_state["impact"] = "skipped_due_to_primary_decision"
        result = dict(primary_result)
        result["advisory_layers"] = {"fxalex": advisory_state}
        return result

    fxalex_module = load_fxalex_module()
    fxalex_snapshot = build_fxalex_snapshot(snapshot, primary_result)
    claims = fxalex_module.load_claims(fxalex_module.CLAIMS_FILE)
    vote_result = fxalex_module.vote_claims(fxalex_snapshot, claims, top_n=30)

    confidence = primary_result["confidence_score"]
    reason_codes = list(primary_result["reason_codes"])
    summary = primary_result["summary"]
    impact = "neutral"

    if vote_result["direction"] == "STRONG_SUPPORT":
        confidence = min(95, confidence + fxalex_config["strong_support_bonus"])
        reason_codes.append("FXALEX_STRONG_SUPPORT")
        summary += f" | fxalex confluence geeft sterke steun (score {vote_result['total_score']})."
        impact = "confidence_up"
    elif vote_result["direction"] == "SUPPORT":
        confidence = min(95, confidence + fxalex_config["support_bonus"])
        reason_codes.append("FXALEX_SUPPORT")
        summary += f" | fxalex confluence ondersteunt de setup (score {vote_result['total_score']})."
        impact = "confidence_up"
    elif vote_result["direction"] == "CONFLICT":
        confidence = max(20, confidence - fxalex_config["conflict_penalty"])
        reason_codes.append("FXALEX_CONFLICT")
        summary += f" | fxalex confluence signaleert conflict (score {vote_result['total_score']})."
        impact = "confidence_down_conflict"
    else:
        confidence = max(20, confidence - fxalex_config["neutral_penalty"])
        reason_codes.append("FXALEX_NEUTRAL")
        summary += " | fxalex confluence is neutraal en verlaagt de confidence licht."
        impact = "confidence_down_neutral"

    advisory_state = {
        "enabled": enabled,
        "used": True,
        "impact": impact,
        "vote_direction": vote_result["direction"],
        "vote_score": vote_result["total_score"],
        "top_claims": vote_result["top_claims"][:3]
    }

    result = {
        "decision": primary_result["decision"],
        "confidence_score": confidence,
        "reason_codes": unique_in_order(reason_codes),
        "summary": summary,
        "advisory_layers": {
            "fxalex": advisory_state
        }
    }
    return result


def maybe_apply_news_context(snapshot: dict, result: dict, skill: dict):
    news_state = news_context.evaluate_news_context(
        snapshot=snapshot,
        config=skill["advisory_layers"]["news_context"],
        base_dir=BASE_DIR,
    )

    result = dict(result)
    advisory_layers = dict(result.get("advisory_layers", {}))
    advisory_layers["news_context"] = news_state
    result["advisory_layers"] = advisory_layers

    if not news_state["used"] or not news_state["reason_codes"]:
        return result

    result["reason_codes"] = unique_in_order(result["reason_codes"] + news_state["reason_codes"])
    if news_state["summary"]:
        result["summary"] = f"{result['summary']} | {news_state['summary']}"

    if news_state["should_wait"] and result["decision"] in ["BUY", "SELL"]:
        result["decision"] = "WAIT"
        result["confidence_score"] = max(20, result["confidence_score"] - news_state["confidence_penalty"])
        result["summary"] = f"{result['summary']} | News context adviseert WAIT door macro-risico."
        return result

    result["confidence_score"] = max(20, result["confidence_score"] - news_state["confidence_penalty"])
    return result


def render_text_report(payload: dict):
    lines = [
        "=" * 100,
        "SET AND FORGET RESULT",
        f"Pair: {payload['pair']} | Timeframe: {payload['execution_timeframe']} | Mode: {payload['execution_mode']}",
        f"Decision: {payload['decision']} | confidence={payload['confidence_score']}",
        f"Reason codes: {payload['reason_codes']}",
        f"Summary: {payload['summary']}"
    ]

    if not payload["validation"]["ok"]:
        lines.append("Errors:")
        for error in payload["validation"]["errors"]:
            lines.append(f"  - {error}")

    return "\n".join(lines)


def emit_payload(payload: dict, output_format: str):
    if output_format == "text":
        print(render_text_report(payload))
        return

    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    print()


def maybe_create_paper_trade(snapshot: dict, payload: dict, log_path: Path):
    payload["paper_trade"]["log_path"] = str(log_path)

    if not paper_trading.should_create_paper_trade(snapshot, payload):
        return payload

    ticket = paper_trading.build_paper_trade_ticket(snapshot, payload)
    paper_trading.append_jsonl(log_path, ticket)
    payload["paper_trade"]["created"] = True
    payload["paper_trade"]["ticket"] = ticket
    return payload


def run_decision_cycle(snapshot: dict, skill: dict, schema: dict, paper_trades_log: Path = PAPER_TRADES_LOG_FILE):
    snapshot_errors = validate_snapshot(snapshot, schema)
    if snapshot_errors:
        payload = build_error_payload(
            snapshot=snapshot,
            error_code="INPUT_SCHEMA_INVALID",
            summary="Snapshot validatie tegen het Set & Forget schema is mislukt.",
            errors=snapshot_errors,
        )
        return payload, 1

    result = evaluate_rules(snapshot, skill)
    result = maybe_apply_fxalex_confluence(snapshot, result, skill)
    result = maybe_apply_news_context(snapshot, result, skill)
    unknown_reason_codes = validate_reason_codes(result["reason_codes"], schema)
    if unknown_reason_codes:
        payload = build_error_payload(
            snapshot=snapshot,
            error_code="OUTPUT_SCHEMA_INVALID",
            summary="Resultaat bevat reason codes die niet in het schema staan.",
            errors=[f"Unknown reason code: {code}" for code in unknown_reason_codes],
        )
        return payload, 1

    payload = build_payload(snapshot, result)
    payload = maybe_create_paper_trade(snapshot, payload, paper_trades_log)
    return payload, 0


def main():
    parser = argparse.ArgumentParser(description="Run the Set & Forget primary decision engine.")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--skill-file", type=Path, default=SKILL_FILE)
    parser.add_argument("--schema-file", type=Path, default=DECISION_SCHEMA_FILE)
    parser.add_argument("--snapshot-file", type=Path, default=LIVE_SNAPSHOT_FILE)
    parser.add_argument("--paper-trades-log", type=Path, default=PAPER_TRADES_LOG_FILE)
    args = parser.parse_args()

    skill = load_json(args.skill_file)
    schema = load_json(args.schema_file)
    snapshot = load_json(args.snapshot_file)
    payload, exit_code = run_decision_cycle(snapshot, skill, schema, args.paper_trades_log)
    emit_payload(payload, args.format)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
