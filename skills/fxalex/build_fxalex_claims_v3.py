import json
import re
from pathlib import Path

INPUT_FILE = Path("/Users/jeroenderaaf/alexbecker_dump/fxalexg/processed/dataset_clean.jsonl")
OUTPUT_FILE = Path("/Users/jeroenderaaf/alexbecker_dump/fxalexg/processed/fxalex_claims_v3.jsonl")

KEYWORDS = {
    "entry": [
        "entry", "enter", "confirmation", "confirm", "breakout",
        "retest", "support", "resistance", "setup", "trigger",
        "pullback", "zone", "aoi"
    ],
    "risk": [
        "risk", "stop loss", "sl", "take profit", "tp",
        "risk reward", "1 to 2", "1 to 3", "rr",
        "position size", "lot size", "minimize my risk"
    ],
    "structure": [
        "trend", "market structure", "higher high", "higher low",
        "lower high", "lower low", "break of structure",
        "liquidity", "liquidity sweep", "range", "bias",
        "bullish", "bearish", "support", "resistance", "ema"
    ],
    "management": [
        "set and forget", "close the trade", "close my trade",
        "breakeven", "move my stop", "leave the trade",
        "let it run", "manage the trade", "partial"
    ],
    "psychology": [
        "discipline", "patience", "emotion", "emotions",
        "greed", "fear", "overtrade", "revenge trade",
        "consistency", "mindset"
    ]
}

NOISE_PATTERNS = [
    "hit that like",
    "subscribe",
    "see you guys in the next one",
    "free telegram",
    "broker i recommend",
    "link in the description",
    "turn trading into your biggest source of income",
    "challenge to turn 100 into 1000000",
    "appreciate you guys",
    "watching this video",
    "my only instagram",
    "if you want to",
]


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def dedupe_consecutive_words(text: str) -> str:
    words = text.split()
    if not words:
        return text

    cleaned = [words[0]]
    for w in words[1:]:
        if w.lower() != cleaned[-1].lower():
            cleaned.append(w)

    return " ".join(cleaned)


def dedupe_repeated_phrases(text: str) -> str:
    words = text.split()
    if not words:
        return text

    cleaned = []
    i = 0

    while i < len(words):
        repeated = False

        for size in range(10, 2, -1):
            if i + 2 * size <= len(words):
                chunk1 = words[i:i+size]
                chunk2 = words[i+size:i+2*size]

                if [x.lower() for x in chunk1] == [x.lower() for x in chunk2]:
                    cleaned.extend(chunk1)
                    i += 2 * size
                    repeated = True
                    break

        if not repeated:
            cleaned.append(words[i])
            i += 1

    return " ".join(cleaned)


def clean_chunk(text: str) -> str:
    text = normalize_spaces(text)
    text = dedupe_consecutive_words(text)
    text = dedupe_repeated_phrases(text)
    text = normalize_spaces(text)

    # HTML entities / rommel
    text = text.replace("&gt;&gt;", "").replace("&gt;", "").replace("&lt;", "")
    text = normalize_spaces(text)

    return text


def split_into_chunks(text: str):
    if not text:
        return []

    text = normalize_spaces(text)

    parts = re.split(r'(?<=[.!?])\s+', text)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) < 3:
        words = text.split()
        parts = []
        chunk_size = 26
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i+chunk_size]).strip()
            if chunk:
                parts.append(chunk)

    return parts


def looks_like_noise(chunk: str) -> bool:
    lower = chunk.lower()
    words = lower.split()

    if len(words) < 7:
        return True

    for pattern in NOISE_PATTERNS:
        if pattern in lower:
            return True

    # teveel herhaling
    unique_ratio = len(set(words)) / max(len(words), 1)
    if unique_ratio < 0.58:
        return True

    # te veel heel korte stopwoordjes / weinig inhoud
    content_words = [w for w in words if len(w) > 3]
    if len(content_words) < 4:
        return True

    # chunk mag niet eindigen in halve onzin
    bad_endings = ["and", "or", "but", "so", "because", "if", "then"]
    if words[-1] in bad_endings:
        return True

    return False


def classify(chunk: str):
    lower = chunk.lower()
    cats = []

    for category, keywords in KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                cats.append(category)
                break

    return cats


def has_strategy_signal(chunk: str):
    lower = chunk.lower()

    strong_signals = [
        "set and forget",
        "risk reward",
        "stop loss",
        "take profit",
        "higher high",
        "higher low",
        "lower high",
        "lower low",
        "break of structure",
        "liquidity",
        "confirmation",
        "retest",
        "bullish",
        "bearish",
        "support",
        "resistance",
        "ema",
        "not trade",
        "entry",
        "setup"
    ]

    return any(sig in lower for sig in strong_signals)


def main():
    total = 0

    with open(INPUT_FILE, "r", encoding="utf-8") as infile, open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
        for line in infile:
            record = json.loads(line)

            transcript = record.get("transcript_clean", "")
            chunks = split_into_chunks(transcript)

            for chunk in chunks:
                chunk = clean_chunk(chunk)

                if looks_like_noise(chunk):
                    continue

                categories = classify(chunk)

                if not categories and not has_strategy_signal(chunk):
                    continue

                claim = {
                    "source": "fxalex",
                    "video_id": record.get("video_id"),
                    "title": record.get("title"),
                    "date": record.get("date"),
                    "url": record.get("url"),
                    "categories": categories,
                    "claim_text": chunk
                }

                outfile.write(json.dumps(claim, ensure_ascii=False) + "\n")
                total += 1

    print("Klaar.")
    print("Claims output:", OUTPUT_FILE)
    print("Aantal gevonden claims:", total)


if __name__ == "__main__":
    main()
