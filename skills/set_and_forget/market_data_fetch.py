import copy
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import market_data_ingest
import runtime_env


BASE_DIR = Path(__file__).resolve().parent
FIXTURE_STORE_FILE = BASE_DIR / "market_data_fetch_fixtures.json"

TWELVEDATA_ADAPTER_KEY = "twelvedata_time_series"
FIXTURE_ADAPTER_KEY = "fixture_scaffold"
DEFAULT_ADAPTER_KEY = TWELVEDATA_ADAPTER_KEY

TWELVEDATA_REQUIRED_ENV_VARS = ["TWELVEDATA_API_KEY"]
TWELVEDATA_OPTIONAL_ENV_VARS = ["TWELVEDATA_BASE_URL", "MARKET_DATA_FETCH_ADAPTER"]
TWELVEDATA_DEFAULT_BASE_URL = "https://api.twelvedata.com"
TWELVEDATA_TIMEFRAMES = {
    "weekly": {"provider_interval": "1week", "outputsize": 12},
    "daily": {"provider_interval": "1day", "outputsize": 20},
    "h4": {"provider_interval": "4h", "outputsize": 24},
}


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def perform_http_get_json(url: str, headers: dict | None = None):
    request = Request(url, headers=headers or {})
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


def build_conservative_risk_features(latest_h4_close: float | None):
    payload = {
        "stop_loss_basis": "unknown",
        "risk_reward_ratio": 0.0,
        "planned_risk_percent": 0.0,
    }
    if latest_h4_close is not None:
        payload["entry_price"] = latest_h4_close
    return payload


def build_conservative_operational_flags():
    return {
        "open_trades_count": 0,
        "high_impact_news_imminent": False,
        "session_window": "unknown",
        "set_and_forget_possible": False,
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

        latest_h4_close = candles["h4"][-1]["close"] if candles["h4"] else None
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
                "objective_context_mode": "conservative_defaults",
            },
            "candles": candles,
            "risk_features": build_conservative_risk_features(latest_h4_close),
            "operational_flags": build_conservative_operational_flags(),
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
        payload = self.http_get_json(url, headers={"Accept": "application/json"})

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
