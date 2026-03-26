import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import market_data_ingest
import market_structure
import runtime_env


BASE_DIR = Path(__file__).resolve().parent
FIXTURE_STORE_FILE = BASE_DIR / "market_data_fetch_fixtures.json"

TWELVEDATA_ADAPTER_KEY = "twelvedata_time_series"
FIXTURE_ADAPTER_KEY = "fixture_scaffold"
DEFAULT_ADAPTER_KEY = TWELVEDATA_ADAPTER_KEY

TWELVEDATA_REQUIRED_ENV_VARS = ["TWELVEDATA_API_KEY"]
TWELVEDATA_OPTIONAL_ENV_VARS = ["TWELVEDATA_BASE_URL", "MARKET_DATA_FETCH_ADAPTER"]
TWELVEDATA_DEFAULT_BASE_URL = "https://api.twelvedata.com"
DEFAULT_HTTP_HEADERS = {
    "Accept": "application/json",
    # Twelve Data currently rejects the default Python urllib signature via Cloudflare.
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
}
TWELVEDATA_TIMEFRAMES = {
    "weekly": {"provider_interval": "1week", "outputsize": 12},
    "daily": {"provider_interval": "1day", "outputsize": 20},
    "h4": {"provider_interval": "4h", "outputsize": 24},
}


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def perform_http_get_json(url: str, headers: dict | None = None):
    request_headers = dict(DEFAULT_HTTP_HEADERS)
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    try:
        with urlopen(request, timeout=15) as response:
            raw_body = response.read().decode("utf-8")
    except HTTPError as error:
        raw_body = error.read().decode("utf-8", errors="replace")
        raise ValueError(f"Twelve Data HTTP {error.code}: {raw_body}") from error
    except URLError as error:
        raise ValueError(f"Twelve Data network error: {error.reason}") from error

    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as error:
        raise ValueError("Twelve Data returned invalid JSON.") from error


def build_market_key(pair: str, execution_timeframe: str):
    return f"{pair}|{execution_timeframe}"


def build_twelvedata_symbol(pair: str):
    token = str(pair or "").strip().upper()
    if not token:
        raise ValueError("Pair is required for market data fetch.")

    if ":" in token:
        token = token.split(":")[-1]
    if "." in token:
        token = token.split(".")[0]
    if "/" in token:
        base, quote = token.split("/", 1)
        if len(base) == 3 and len(quote) == 3:
            return f"{base}/{quote}"
    if len(token) == 6:
        return f"{token[:3]}/{token[3:]}"
    raise ValueError(f"Unsupported pair format for Twelve Data: {pair!r}")


def normalize_provider_timestamp(raw_value: str):
    token = str(raw_value).strip()
    if not token:
        raise ValueError("Provider candle timestamp is required.")
    if token.endswith("Z") or ("+" in token[10:] or "-" in token[10:]):
        return token.replace(" ", "T")
    if " " in token:
        return f"{token.replace(' ', 'T')}Z"
    if len(token) == 10:
        return f"{token}T00:00:00Z"
    return token


def normalize_provider_candle(candle: dict):
    try:
        return {
            "timestamp": normalize_provider_timestamp(candle["datetime"]),
            "open": float(candle["open"]),
            "high": float(candle["high"]),
            "low": float(candle["low"]),
            "close": float(candle["close"]),
        }
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid provider candle payload: {candle!r}") from error


def parse_iso_timestamp(value: str | None):
    if not value:
        return None
    token = str(value).strip()
    if not token:
        return None
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    parsed = datetime.fromisoformat(token)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def derive_session_window(reference_timestamp: str | None):
    timestamp = parse_iso_timestamp(reference_timestamp)
    if timestamp is None:
        return "unknown"

    london = timestamp.astimezone(ZoneInfo("Europe/London"))
    new_york = timestamp.astimezone(ZoneInfo("America/New_York"))
    if london.weekday() > 4 or new_york.weekday() > 4:
        return "outside_overlap"

    london_open = 8 <= london.hour < 17
    new_york_open = 8 <= new_york.hour < 17
    if london_open and new_york_open:
        return "london_newyork_overlap"
    if london_open:
        return "london_session"
    return "outside_overlap"


def derive_planned_entry_price(candles: dict, higher_trend: str, weekly_state: dict, daily_state: dict, h4_state: dict):
    if higher_trend not in {"bullish", "bearish"}:
        return None

    swing_high, swing_low = market_structure.determine_aoi_impulse_bounds(
        weekly_state,
        daily_state,
        h4_state,
        {
            "weekly": {"candles": candles["weekly"]},
            "daily": {"candles": candles["daily"]},
            "h4": {"candles": candles["h4"]},
        },
    )
    fib_zone = market_structure.compute_fib_zone(higher_trend, swing_high, swing_low)
    if not fib_zone:
        return None
    zone_low, zone_high = fib_zone
    return (zone_low + zone_high) / 2


def derive_stop_and_target_prices(candles: dict, higher_trend: str, h4_state: dict, entry_price: float | None):
    h4_candles = candles["h4"]
    if not h4_candles or higher_trend not in {"bullish", "bearish"}:
        return None

    if entry_price is None:
        entry_price = h4_candles[-1]["close"]
    recent_h4 = h4_candles[-7:]
    if higher_trend == "bullish":
        stop_loss_price = h4_state.get("last_confirmed_low")
        if stop_loss_price is None:
            stop_loss_price = min(candle["low"] for candle in recent_h4)
        risk_distance = entry_price - stop_loss_price
        if risk_distance <= 0:
            return None
        take_profit_price = entry_price + (risk_distance * 2.0)
        return {
            "entry_price": entry_price,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "stop_loss_basis": "last_swing",
            "risk_reward_ratio": 2.0,
            "planned_risk_percent": 1.0,
        }

    stop_loss_price = h4_state.get("last_confirmed_high")
    if stop_loss_price is None:
        stop_loss_price = max(candle["high"] for candle in recent_h4)
    risk_distance = stop_loss_price - entry_price
    if risk_distance <= 0:
        return None
    take_profit_price = entry_price - (risk_distance * 2.0)
    return {
        "entry_price": entry_price,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "stop_loss_basis": "last_swing",
        "risk_reward_ratio": 2.0,
        "planned_risk_percent": 1.0,
    }


def build_default_risk_features(latest_h4_close: float | None):
    risk_features = {
        "stop_loss_basis": "unknown",
        "risk_reward_ratio": 0.0,
        "planned_risk_percent": 0.0,
    }
    if latest_h4_close is not None:
        risk_features["entry_price"] = latest_h4_close
    return risk_features


def build_default_operational_flags(session_window: str):
    return {
        "open_trades_count": 0,
        "high_impact_news_imminent": False,
        "session_window": session_window,
        "set_and_forget_possible": False,
    }


def derive_objective_context_from_candles(candles: dict, request_payload: dict):
    weekly_state = market_structure.analyze_timeframe_structure(candles["weekly"])
    daily_state = market_structure.analyze_timeframe_structure(candles["daily"])
    higher_trend = market_structure.infer_higher_trend(weekly_state, daily_state)
    h4_state = market_structure.infer_h4_features(candles["h4"], higher_trend)
    reference_timestamp = request_payload.get("trigger_time") or candles["h4"][-1]["timestamp"]
    session_window = derive_session_window(reference_timestamp)
    latest_h4_close = candles["h4"][-1]["close"] if candles["h4"] else None

    risk_features = build_default_risk_features(latest_h4_close)
    planned_entry_price = derive_planned_entry_price(candles, higher_trend, weekly_state, daily_state, h4_state)
    derived_trade_plan = derive_stop_and_target_prices(candles, higher_trend, h4_state, planned_entry_price)
    if derived_trade_plan is not None:
        risk_features.update(derived_trade_plan)

    operational_flags = build_default_operational_flags(session_window)
    operational_flags["set_and_forget_possible"] = derived_trade_plan is not None

    return {
        "higher_trend": higher_trend,
        "weekly_state": weekly_state,
        "daily_state": daily_state,
        "h4_state": h4_state,
        "risk_features": risk_features,
        "operational_flags": operational_flags,
    }


class MarketDataFetchAdapter:
    adapter_key = "base"

    def fetch_market_data(self, request_payload: dict):
        raise NotImplementedError


class FixtureScaffoldMarketDataAdapter(MarketDataFetchAdapter):
    adapter_key = FIXTURE_ADAPTER_KEY

    def __init__(self, fixture_store: dict):
        self.fixture_store = fixture_store

    def fetch_market_data(self, request_payload: dict):
        market_key = build_market_key(
            request_payload["pair"],
            request_payload["execution_timeframe"],
        )
        market = self.fixture_store.get("markets", {}).get(market_key)
        if market is None:
            available = sorted(self.fixture_store.get("markets", {}).keys())
            raise LookupError(
                f"No market data scaffold available for {market_key}. Available fixtures: {available}"
            )
        return copy.deepcopy(market)


class TwelveDataTimeSeriesAdapter(MarketDataFetchAdapter):
    adapter_key = TWELVEDATA_ADAPTER_KEY

    def __init__(self, base_dir: Path, http_get_json=None):
        self.base_dir = base_dir
        self.http_get_json = http_get_json or perform_http_get_json
        self.env_state = runtime_env.load_standardized_env(base_dir)
        self.runtime_config = runtime_env.summarize_env_keys(
            TWELVEDATA_REQUIRED_ENV_VARS,
            TWELVEDATA_OPTIONAL_ENV_VARS,
        )
        self.api_key = os.environ.get("TWELVEDATA_API_KEY")
        self.base_url = os.environ.get("TWELVEDATA_BASE_URL", TWELVEDATA_DEFAULT_BASE_URL).rstrip("/")

    def fetch_market_data(self, request_payload: dict):
        if not self.api_key:
            raise ValueError(
                "TWELVEDATA_API_KEY is required for the twelvedata_time_series adapter."
            )

        provider_symbol = build_twelvedata_symbol(request_payload["pair"])
        candles = {}
        for timeframe, config in TWELVEDATA_TIMEFRAMES.items():
            candles[timeframe] = self.fetch_time_series(
                provider_symbol=provider_symbol,
                interval=config["provider_interval"],
                outputsize=config["outputsize"],
            )

        objective_context = derive_objective_context_from_candles(candles, request_payload)
        return {
            "fetch_context": {
                "provider": "twelvedata",
                "adapter": self.adapter_key,
                "provider_symbol": provider_symbol,
                "base_url": self.base_url,
                "timeframes": {
                    timeframe: config["provider_interval"]
                    for timeframe, config in TWELVEDATA_TIMEFRAMES.items()
                },
                "env": {
                    "configured": self.runtime_config["configured"],
                    "present_required_env_vars": self.runtime_config["present_required_env_vars"],
                    "missing_required_env_vars": self.runtime_config["missing_required_env_vars"],
                    "files_loaded": self.env_state["files_loaded"],
                },
                "objective_context_mode": "derived_from_candles",
                "derived_higher_trend": objective_context["higher_trend"],
                "derived_session_window": objective_context["operational_flags"]["session_window"],
            },
            "candles": candles,
            "risk_features": objective_context["risk_features"],
            "operational_flags": objective_context["operational_flags"],
        }

    def fetch_time_series(self, provider_symbol: str, interval: str, outputsize: int):
        params = {
            "symbol": provider_symbol,
            "interval": interval,
            "outputsize": outputsize,
            "timezone": "UTC",
            "order": "asc",
            "format": "JSON",
            "apikey": self.api_key,
        }
        url = f"{self.base_url}/time_series?{urlencode(params)}"
        payload = self.http_get_json(url)

        if payload.get("status") == "error":
            raise ValueError(payload.get("message", "Twelve Data returned an error."))

        values = payload.get("values")
        if not isinstance(values, list) or not values:
            raise ValueError(
                f"Twelve Data returned no candle values for {provider_symbol} at {interval}."
            )

        candles = sorted(
            (normalize_provider_candle(item) for item in values),
            key=lambda candle: candle["timestamp"],
        )
        if len(candles) < 7:
            raise ValueError(
                f"Twelve Data returned too few candles for {provider_symbol} at {interval}."
            )
        return candles


def get_adapter(adapter_key: str | None = None, fixture_store: dict | None = None):
    runtime_env.load_standardized_env(BASE_DIR)
    selected_adapter = adapter_key or os.environ.get("MARKET_DATA_FETCH_ADAPTER", DEFAULT_ADAPTER_KEY)
    if selected_adapter == FIXTURE_ADAPTER_KEY:
        return FixtureScaffoldMarketDataAdapter(fixture_store or load_json(FIXTURE_STORE_FILE))
    if selected_adapter == TWELVEDATA_ADAPTER_KEY:
        return TwelveDataTimeSeriesAdapter(BASE_DIR)
    raise ValueError(f"Unsupported market data adapter: {selected_adapter}")


def prepare_trigger_request_payload(trigger_payload: dict):
    ingest_schema = load_json(market_data_ingest.INGEST_SCHEMA_FILE)
    return {
        "pair": market_data_ingest.normalize_pair(
            trigger_payload.get("pair") or trigger_payload.get("symbol") or trigger_payload.get("ticker")
        ),
        "execution_timeframe": market_data_ingest.normalize_timeframe(
            trigger_payload.get("execution_timeframe") or trigger_payload.get("timeframe") or trigger_payload.get("interval"),
            ingest_schema,
        ),
        "execution_mode": trigger_payload.get("execution_mode", "paper"),
        "trigger_time": trigger_payload.get("trigger_time"),
        "fxalex_confluence_enabled": trigger_payload.get("fxalex_confluence_enabled", False),
        "news_context_enabled": trigger_payload.get("news_context_enabled", False),
    }


def build_ingest_payload_from_fetch(trigger_request: dict, fetched_market_data: dict):
    ingest_payload = {
        "pair": trigger_request["pair"],
        "execution_timeframe": trigger_request["execution_timeframe"],
        "execution_mode": trigger_request["execution_mode"],
        "source_kind": "market_data_pipeline",
        "generated_at": trigger_request.get("trigger_time"),
        "fxalex_confluence_enabled": trigger_request.get("fxalex_confluence_enabled", False),
        "news_context_enabled": trigger_request.get("news_context_enabled", False),
        "candles": fetched_market_data["candles"],
        "risk_features": fetched_market_data["risk_features"],
        "operational_flags": fetched_market_data["operational_flags"],
    }
    if fetched_market_data.get("aoi_features") is not None:
        ingest_payload["aoi_features"] = fetched_market_data["aoi_features"]
    if fetched_market_data.get("confirmation_features") is not None:
        ingest_payload["confirmation_features"] = fetched_market_data["confirmation_features"]
    return ingest_payload


def run_trigger_fetch_prep(
    trigger_payload: dict,
    adapter: MarketDataFetchAdapter | None = None,
):
    adapter = adapter or get_adapter()
    trigger_request = prepare_trigger_request_payload(trigger_payload)

    try:
        fetched_market_data = adapter.fetch_market_data(trigger_request)
    except (LookupError, ValueError) as error:
        return {
            "status": "market_data_fetch_error",
            "errors": [str(error)],
            "adapter": adapter.adapter_key,
            "trigger_request": trigger_request,
            "ingest_payload": None,
            "fetch_context": None,
        }, 1

    ingest_payload = build_ingest_payload_from_fetch(trigger_request, fetched_market_data)
    ingest_schema = load_json(market_data_ingest.INGEST_SCHEMA_FILE)
    ingest_errors = market_data_ingest.validate_ingest_payload(ingest_payload, ingest_schema)
    if ingest_errors:
        return {
            "status": "invalid_market_data_fetch_payload",
            "errors": ingest_errors,
            "adapter": adapter.adapter_key,
            "trigger_request": trigger_request,
            "ingest_payload": ingest_payload,
            "fetch_context": fetched_market_data.get("fetch_context"),
        }, 1

    return {
        "status": "prepared",
        "errors": [],
        "adapter": adapter.adapter_key,
        "trigger_request": trigger_request,
        "ingest_payload": ingest_payload,
        "fetch_context": fetched_market_data.get("fetch_context", {}),
    }, 0
