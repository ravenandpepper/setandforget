import json
from pathlib import Path

BASE_DIR = Path("/Users/jeroenderaaf/sites/setandforget/skills/fxalex")
CLAIMS_FILE = Path("/Users/jeroenderaaf/alexbecker_dump/fxalexg/processed/fxalex_claims_v2.jsonl")
EXAMPLES_FILE = BASE_DIR / "fxalex_decision_examples.json"


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


def load_claims():
    rows = []
    with open(CLAIMS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def score_claim_text(text: str, example: dict):
    text_lower = text.lower()
    score = 0
    tags = []

    # Direction match
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

    # Structure alignment
    if example["market_structure_state"] == "bullish_confirmed":
        if "bullish" in text_lower or "higher high" in text_lower or "higher low" in text_lower:
            score += 2
            tags.append("STRUCTURE_SUPPORTS")
    elif example["market_structure_state"] == "bearish_confirmed":
        if "bearish" in text_lower or "lower high" in text_lower or "lower low" in text_lower:
            score += 2
            tags.append("STRUCTURE_SUPPORTS")

    # Confirmation
    if example["confirmation_present"] and "confirmation" in text_lower:
        score += 1
        tags.append("CONFIRMATION_SUPPORTS")

    # Risk alignment
    if any(h in text_lower for h in RISK_HINTS):
        if example["risk_reward_ratio"] >= 2.0:
            score += 1
            tags.append("RISK_FRAME_SUPPORTS")
        else:
            score -= 1
            tags.append("RISK_FRAME_CONFLICTS")

    # Management alignment
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


def decide_from_vote(example: dict, vote_result: dict):
    direction = vote_result["direction"]
    total_score = vote_result["total_score"]

    if not example["confirmation_present"]:
        return {
            "decision": "WAIT",
            "confidence_score": 30,
            "summary": "Confirmation ontbreekt, dus geen trade.",
            "vote_score": total_score
        }

    if example["risk_reward_ratio"] < 2.0:
        return {
            "decision": "NO-GO",
            "confidence_score": 25,
            "summary": "Risk/reward onder minimum.",
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
        "confidence_score": max(35, 50 + total_score),
        "summary": "Claims geven onvoldoende steun voor een overtuigende trade.",
        "vote_score": total_score
    }


def main():
    claims = load_claims()

    with open(EXAMPLES_FILE, "r", encoding="utf-8") as f:
        examples = json.load(f)["examples"]

    for ex in examples:
        vote_result = vote_claims(ex, claims, top_n=30)
        final = decide_from_vote(ex, vote_result)

        print("=" * 90)
        print(f"Example: {ex['name']}")
        print(f"Pair: {ex['pair']} | Timeframe: {ex['timeframe']} | Bias: {ex['bias']}")
        print(f"Decision: {final['decision']}")
        print(f"Confidence: {final['confidence_score']}")
        print(f"Vote score: {final['vote_score']}")
        print(f"Summary: {final['summary']}")
        print("Top supporting claims:")

        for item in vote_result["top_claims"][:5]:
            print(f"  - score={item['score']} | tags={item['tags']} | text={item['claim_text'][:180]}")


if __name__ == "__main__":
    main()
