import json
import os
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import market_data_fetch


BASE_DIR = Path(__file__).resolve().parent
TRIGGER_ONLY_ALERT_FILE = BASE_DIR / "tradingview_trigger_only_alert.example.json"
PROVIDER_FIXTURES_FILE = BASE_DIR / "market_data_fetch_provider_fixtures.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def build_mock_http_get(provider_fixtures: dict):
    def _mock_http_get(url: str, headers: dict | None = None):
        query = parse_qs(urlparse(url).query)
        key = f"{query['symbol'][0]}|{query['interval'][0]}"
        if key not in provider_fixtures["time_series"]:
            raise AssertionError(f"Unexpected provider fixture key: {key}")
        return deepcopy(provider_fixtures["time_series"][key])

    return _mock_http_get


def run_valid_case():
    payload = load_json(TRIGGER_ONLY_ALERT_FILE)
    provider_fixtures = load_json(PROVIDER_FIXTURES_FILE)
    with patch.dict(
        os.environ,
        {
            "TWELVEDATA_API_KEY": "test-api-key",
            "MARKET_DATA_FETCH_ADAPTER": market_data_fetch.TWELVEDATA_ADAPTER_KEY,
        },
        clear=True,
    ), patch.object(
        market_data_fetch.runtime_env,
        "env_file_candidates",
        return_value=[],
    ), patch.object(
        market_data_fetch,
        "perform_http_get_json",
        side_effect=build_mock_http_get(provider_fixtures),
    ):
        result, exit_code = market_data_fetch.run_trigger_fetch_prep(payload)

    assert exit_code == 0, "valid trigger-only fetch should succeed"
    assert result["status"] == "prepared", "valid trigger-only fetch should prepare ingest payload"
    assert result["adapter"] == market_data_fetch.TWELVEDATA_ADAPTER_KEY, "Twelve Data adapter should be used by default"
    assert result["fetch_context"]["provider"] == "twelvedata", "provider should be Twelve Data"
    assert result["ingest_payload"]["pair"] == "EURUSD", "pair should normalize to EURUSD"
    assert result["ingest_payload"]["execution_timeframe"] == "4H", "timeframe should normalize to 4H"
    assert len(result["ingest_payload"]["candles"]["h4"]) >= 7, "h4 candles must be present"
    assert result["ingest_payload"]["risk_features"]["stop_loss_basis"] == "last_swing", (
        "real candle fetch should derive a last-swing stop basis from the fetched candles"
    )
    assert result["ingest_payload"]["risk_features"]["risk_reward_ratio"] == 2.0, (
        "real candle fetch should derive a baseline 1:2 risk/reward plan from candles"
    )
    assert result["ingest_payload"]["operational_flags"]["session_window"] == "london_newyork_overlap", (
        "trigger timestamp during overlap should map to london_newyork_overlap"
    )
    assert result["ingest_payload"]["operational_flags"]["set_and_forget_possible"] is True, (
        "derived candle-based trade plan should mark the setup as set-and-forget possible"
    )
    assert result["fetch_context"]["derived_higher_trend"] == "bullish", (
        "fixture candles should derive a bullish higher timeframe trend"
    )
    assert result["fetch_context"]["derived_session_window"] == "london_newyork_overlap", (
        "fetch context should expose the derived overlap session"
    )
    return {
        "id": "trigger_only_twelvedata_adapter_prepares_ingest_payload",
        "adapter": result["adapter"],
        "pair": result["ingest_payload"]["pair"],
    }


def run_london_session_derivation_case():
    session_window = market_data_fetch.derive_session_window("2026-03-27T08:00:00Z")
    assert session_window == "london_session", (
        "European morning before New York should derive london_session"
    )
    return {
        "id": "trigger_timestamp_in_european_morning_maps_to_london_session",
        "session_window": session_window,
    }


def run_missing_api_key_case():
    payload = load_json(TRIGGER_ONLY_ALERT_FILE)
    with patch.dict(
        os.environ,
        {"MARKET_DATA_FETCH_ADAPTER": market_data_fetch.TWELVEDATA_ADAPTER_KEY},
        clear=True,
    ), patch.object(
        market_data_fetch.runtime_env,
        "env_file_candidates",
        return_value=[],
    ):
        result, exit_code = market_data_fetch.run_trigger_fetch_prep(payload)

    assert exit_code == 1, "missing API key should fail"
    assert result["status"] == "market_data_fetch_error", "missing API key should produce fetch error"
    assert "TWELVEDATA_API_KEY" in result["errors"][0], "missing API key error should be explicit"
    return {
        "id": "trigger_only_missing_api_key_returns_fetch_error",
        "status": result["status"],
    }


def main():
    valid = run_valid_case()
    london = run_london_session_derivation_case()
    missing = run_missing_api_key_case()
    print("PASS 3/3 market data fetch scenarios")
    print(f"- {valid['id']}: adapter={valid['adapter']} pair={valid['pair']}")
    print(f"- {london['id']}: session_window={london['session_window']}")
    print(f"- {missing['id']}: status={missing['status']}")


if __name__ == "__main__":
    main()
