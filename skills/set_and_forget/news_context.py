import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BRAVE_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

CURRENCY_NAMES = {
    "EUR": "euro",
    "USD": "us dollar",
    "GBP": "british pound",
    "JPY": "japanese yen",
    "CHF": "swiss franc",
    "AUD": "australian dollar",
    "NZD": "new zealand dollar",
    "CAD": "canadian dollar",
}

CENTRAL_BANK_TERMS = {
    "EUR": ["ECB", "European Central Bank"],
    "USD": ["Fed", "Federal Reserve", "FOMC"],
    "GBP": ["BoE", "Bank of England"],
    "JPY": ["BoJ", "Bank of Japan"],
    "CHF": ["SNB", "Swiss National Bank"],
    "AUD": ["RBA", "Reserve Bank of Australia"],
    "NZD": ["RBNZ", "Reserve Bank of New Zealand"],
    "CAD": ["BoC", "Bank of Canada"],
}

HIGH_IMPACT_KEYWORDS = [
    "cpi",
    "nfp",
    "payrolls",
    "inflation",
    "rate decision",
    "interest rate",
    "central bank",
    "fomc",
    "ecb",
    "boj",
    "boe",
    "snb",
    "rba",
    "rbnz",
    "boc",
]

VOLATILITY_KEYWORDS = [
    "geopolitical",
    "war",
    "attack",
    "sanctions",
    "tariff",
    "emergency",
    "volatility",
    "market turmoil",
    "risk-off",
    "flash crash",
]


def load_env_file(path: Path):
    if not path.exists():
        return

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_env_context(base_dir: Path):
    workspace_root = base_dir.parent.parent
    for candidate in [workspace_root / ".env", base_dir / ".env"]:
        load_env_file(candidate)


def currency_terms_from_pair(pair: str):
    base = pair[:3].upper()
    quote = pair[3:6].upper()
    terms = [base, quote, CURRENCY_NAMES.get(base, base.lower()), CURRENCY_NAMES.get(quote, quote.lower())]
    for code in [base, quote]:
        terms.extend(CENTRAL_BANK_TERMS.get(code, []))
    return terms


def build_query(pair: str):
    joined = " ".join(dict.fromkeys(currency_terms_from_pair(pair)))
    return (
        f"{joined} high impact economic events central bank announcement "
        f"geopolitical volatility warning"
    )


def perform_brave_search(api_key: str, query: str, freshness: str = "pd", count: int = 5):
    params = urlencode({
        "q": query,
        "freshness": freshness,
        "count": count,
        "search_lang": "en",
        "country": "US",
    })
    request = Request(
        f"{BRAVE_SEARCH_ENDPOINT}?{params}",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        },
    )
    with urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def analyze_results(pair: str, results: list):
    reason_codes = []
    notes = []

    all_cb_terms = [term.lower() for terms in CENTRAL_BANK_TERMS.values() for term in terms]

    for item in results:
        text = " ".join([
            str(item.get("title", "")),
            str(item.get("description", "")),
            " ".join(item.get("extra_snippets", [])),
        ]).lower()

        if any(keyword in text for keyword in HIGH_IMPACT_KEYWORDS) and "HIGH_IMPACT_NEWS" not in reason_codes:
            reason_codes.append("HIGH_IMPACT_NEWS")
            notes.append(f"Brave Search signaleert high-impact macrocontext voor {pair}.")

        if any(term in text for term in all_cb_terms) and "CENTRAL_BANK_EVENT" not in reason_codes:
            reason_codes.append("CENTRAL_BANK_EVENT")
            notes.append(f"Brave Search noemt een centrale bankgerelateerde gebeurtenis voor {pair}.")

        if any(keyword in text for keyword in VOLATILITY_KEYWORDS) and "MACRO_VOLATILITY_WARNING" not in reason_codes:
            reason_codes.append("MACRO_VOLATILITY_WARNING")
            notes.append(f"Brave Search detecteert verhoogde macro- of geopolitieke volatiliteit voor {pair}.")

    should_wait = any(code in reason_codes for code in ["HIGH_IMPACT_NEWS", "CENTRAL_BANK_EVENT"])
    confidence_penalty = 0
    if should_wait:
        confidence_penalty = 10
    elif "MACRO_VOLATILITY_WARNING" in reason_codes:
        confidence_penalty = 6

    return {
        "reason_codes": reason_codes,
        "summary": " | ".join(notes),
        "should_wait": should_wait,
        "confidence_penalty": confidence_penalty,
    }


def evaluate_news_context(snapshot: dict, config: dict, base_dir: Path):
    enabled = snapshot.get("news_context_enabled", config.get("enabled_by_default", False))
    if not enabled:
        return {
            "enabled": False,
            "used": False,
            "impact": "not_applied",
            "reason_codes": [],
            "summary": "",
            "should_wait": False,
            "confidence_penalty": 0,
        }

    load_env_context(base_dir)
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return {
            "enabled": True,
            "used": False,
            "impact": "unavailable_missing_api_key",
            "reason_codes": [],
            "summary": "",
            "should_wait": False,
            "confidence_penalty": 0,
        }

    query = build_query(snapshot["pair"])
    try:
        response = perform_brave_search(
            api_key=api_key,
            query=query,
            freshness=config.get("freshness", "pd"),
            count=config.get("result_count", 5),
        )
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return {
            "enabled": True,
            "used": False,
            "impact": "unavailable_api_error",
            "reason_codes": [],
            "summary": "",
            "should_wait": False,
            "confidence_penalty": 0,
        }

    results = response.get("web", {}).get("results", [])
    analysis = analyze_results(snapshot["pair"], results)

    impact = "informational"
    if analysis["should_wait"]:
        impact = "wait_advisory"
    elif analysis["confidence_penalty"] > 0:
        impact = "confidence_down"

    return {
        "enabled": True,
        "used": True,
        "impact": impact,
        "reason_codes": analysis["reason_codes"],
        "summary": analysis["summary"],
        "should_wait": analysis["should_wait"],
        "confidence_penalty": analysis["confidence_penalty"],
        "query": query,
        "result_count": len(results),
    }
