import json
from pathlib import Path

BASE_DIR = Path("/Users/jeroenderaaf/sites/setandforget/skills/fxalex")

SKILL_FILE = BASE_DIR / "fxalex_skill_v2.json"
EXAMPLES_FILE = BASE_DIR / "fxalex_decision_examples.json"


def evaluate(example, skill):

    mode = example["mode"]
    mode_config = skill["modes"][mode]

    reason_codes = []
    notes = []

    # -----------------------------
    # HARD GATES
    # -----------------------------

    if example["bias"] in ["neutral", "unknown"]:
        return {
            "decision": "WAIT",
            "confidence_score": 35,
            "reason_codes": ["BIAS_UNKNOWN"],
            "summary": "Geen duidelijke bias, dus wachten.",
            "mode_used": mode
        }

    if example["market_structure_state"] in ["range", "unclear"]:
        return {
            "decision": "WAIT",
            "confidence_score": 35,
            "reason_codes": ["STRUCTURE_UNCLEAR"],
            "summary": "Market structure is niet duidelijk.",
            "mode_used": mode
        }

    if example["confirmation_present"] is False:
        return {
            "decision": "WAIT",
            "confidence_score": 30,
            "reason_codes": ["CONFIRMATION_MISSING"],
            "summary": "Confirmation ontbreekt.",
            "mode_used": mode
        }

    if example["risk_reward_ratio"] < mode_config["min_risk_reward"]:
        return {
            "decision": "NO-GO",
            "confidence_score": 25,
            "reason_codes": ["RR_TOO_LOW"],
            "summary": "Risk/Reward onder minimum.",
            "mode_used": mode
        }

    if example["planned_risk_percent"] > mode_config["max_risk_percent"]:
        return {
            "decision": "NO-GO",
            "confidence_score": 25,
            "reason_codes": ["RISK_TOO_HIGH"],
            "summary": "Gepland risico te hoog.",
            "mode_used": mode
        }

    if example["setup_quality"] < mode_config["min_setup_quality"]:
        return {
            "decision": "WAIT",
            "confidence_score": 40,
            "reason_codes": ["SETUP_TOO_WEAK"],
            "summary": "Setupkwaliteit te laag.",
            "mode_used": mode
        }

    if example["set_and_forget_possible"] is False:
        return {
            "decision": "WAIT",
            "confidence_score": 40,
            "reason_codes": ["SET_AND_FORGET_NOT_POSSIBLE"],
            "summary": "Set & Forget niet mogelijk.",
            "mode_used": mode
        }

    if example["trader_condition"] in ["tired", "traveling", "distracted"]:
        return {
            "decision": "WAIT",
            "confidence_score": 35,
            "reason_codes": ["TRADER_STATE_BAD"],
            "summary": "Trader conditie niet goed.",
            "mode_used": mode
        }

    # -----------------------------
    # DIRECTION LOGIC
    # -----------------------------

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
            "mode_used": mode
        }

    # -----------------------------
    # CONFIDENCE ADJUSTMENTS
    # -----------------------------

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
        "mode_used": mode
    }


def main():

    with open(SKILL_FILE, "r", encoding="utf-8") as f:
        skill = json.load(f)

    with open(EXAMPLES_FILE, "r", encoding="utf-8") as f:
        examples = json.load(f)["examples"]

    for ex in examples:

        result = evaluate(ex, skill)

        print("=" * 80)
        print(f"Example: {ex['name']}")
        print(f"Pair: {ex['pair']} | Timeframe: {ex['timeframe']} | Mode: {ex['mode']}")
        print(f"Decision: {result['decision']}")
        print(f"Confidence: {result['confidence_score']}")
        print(f"Summary: {result['summary']}")
        print(f"Reason codes: {result['reason_codes']}")


if __name__ == "__main__":
    main()
