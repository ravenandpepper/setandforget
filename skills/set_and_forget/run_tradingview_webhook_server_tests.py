import http.client
import json
import os
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import market_data_fetch
import run_set_and_forget as engine
import run_structured_automation as automation
import tradingview_webhook
import tradingview_webhook_server as server_module


BASE_DIR = Path(__file__).resolve().parent
ALERT_FILE = BASE_DIR / "tradingview_alert.example.json"
CANDLE_ALERT_FILE = BASE_DIR / "tradingview_candle_alert.example.json"
TRIGGER_ONLY_ALERT_FILE = BASE_DIR / "tradingview_trigger_only_alert.example.json"
PROVIDER_FIXTURES_FILE = BASE_DIR / "market_data_fetch_provider_fixtures.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def request_json(method: str, host: str, port: int, path: str, body: dict | None = None):
    connection = http.client.HTTPConnection(host, port, timeout=5)
    payload = None
    headers = {}
    if body is not None:
        payload = json.dumps(body)
        headers["Content-Type"] = "application/json"

    connection.request(method, path, body=payload, headers=headers)
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    return response.status, json.loads(raw.decode("utf-8"))


def build_mock_http_get(provider_fixtures: dict):
    def _mock_http_get(url: str, headers: dict | None = None):
        query = parse_qs(urlparse(url).query)
        key = f"{query['symbol'][0]}|{query['interval'][0]}"
        if key not in provider_fixtures["time_series"]:
            raise AssertionError(f"Unexpected provider fixture key: {key}")
        return deepcopy(provider_fixtures["time_series"][key])

    return _mock_http_get


def run_server_case(alert_payload: dict, path: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        paper_trades_log = tmp_path / "paper_trades_log.jsonl"
        decision_log = tmp_path / "automation_decisions_log.jsonl"
        runs_dir = tmp_path / "automation_runs"
        tournament_sidecar_config_file = tmp_path / "live_tournament_sidecar.json"
        tournament_sidecar_config_file.write_text('{"enabled": false}\n', encoding="utf-8")

        server, config = server_module.serve(
            host="127.0.0.1",
            port=0,
            route=server_module.DEFAULT_ROUTE,
            trigger_only_route=server_module.DEFAULT_TRIGGER_ONLY_ROUTE,
            health_route=server_module.DEFAULT_HEALTH_ROUTE,
            webhook_schema_file=tradingview_webhook.WEBHOOK_SCHEMA_FILE,
            skill_file=engine.SKILL_FILE,
            decision_schema_file=engine.DECISION_SCHEMA_FILE,
            paper_trades_log=paper_trades_log,
            runs_dir=runs_dir,
            decision_log=decision_log,
            tournament_sidecar_config_file=tournament_sidecar_config_file,
        )
        host, port = server.server_address
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            health_status, health_body = request_json("GET", host, port, config["health_route"])
            post_status, post_body = request_json("POST", host, port, path, alert_payload)
            wrong_route_status, wrong_route_body = request_json("POST", host, port, "/wrong-route", alert_payload)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        return {
            "health_status": health_status,
            "health_body": health_body,
            "post_status": post_status,
            "post_body": post_body,
            "wrong_route_status": wrong_route_status,
            "wrong_route_body": wrong_route_body,
        }


def main():
    bullish_alert = load_json(ALERT_FILE)
    candle_alert = load_json(CANDLE_ALERT_FILE)
    trigger_only_alert = load_json(TRIGGER_ONLY_ALERT_FILE)
    provider_fixtures = load_json(PROVIDER_FIXTURES_FILE)
    result = run_server_case(bullish_alert, server_module.DEFAULT_ROUTE)

    assert result["health_status"] == 200, "Health route must return 200"
    assert result["health_body"]["status"] == "ok", "Health route must report ok"
    assert result["post_status"] == 200, "Valid TradingView POST must return 200"
    assert result["post_body"]["status"] == "processed", "Webhook POST must be processed"
    assert result["post_body"]["automation"]["payload"]["decision"] == "BUY", (
        "Webhook server must route the alert into the existing BUY flow"
    )
    assert result["post_body"]["automation"]["run"]["paper_trade_created"] is True, (
        "Webhook server must preserve paper-trade creation for BUY"
    )
    assert result["wrong_route_status"] == 404, "Unknown route must return 404"
    assert result["wrong_route_body"]["status"] == "not_found", "Unknown route must report not_found"

    invalid_result = run_server_case({"source": "tradingview"}, server_module.DEFAULT_ROUTE)
    assert invalid_result["post_status"] == 422, "Invalid TradingView payload must return 422"
    assert invalid_result["post_body"]["status"] in {"invalid_alert", "invalid_snapshot"}, (
        "Invalid TradingView payload must fail validation"
    )

    candle_result = run_server_case(candle_alert, server_module.DEFAULT_ROUTE)
    assert candle_result["post_status"] == 200, "Valid candle-bundle TradingView POST must return 200"
    assert candle_result["post_body"]["status"] == "processed", "Candle-bundle webhook POST must be processed"
    assert candle_result["post_body"]["automation"]["payload"]["decision"] == "BUY", (
        "Webhook server must route the candle bundle into the BUY flow"
    )
    assert candle_result["post_body"]["automation"]["run"]["paper_trade_created"] is True, (
        "Webhook server must preserve paper-trade creation for candle-bundle BUY"
    )

    trigger_only_alert.pop("payload_kind", None)
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
        trigger_only_result = run_server_case(trigger_only_alert, server_module.DEFAULT_TRIGGER_ONLY_ROUTE)

    assert trigger_only_result["post_status"] == 200, "Valid trigger-only TradingView POST must return 200"
    assert trigger_only_result["post_body"]["status"] == "processed", "Trigger-only webhook POST must be processed"
    assert trigger_only_result["post_body"]["market_data_fetch"]["status"] == "prepared", (
        "Trigger-only webhook must prepare server-side market data"
    )
    assert trigger_only_result["post_body"]["market_data_fetch"]["adapter"] == market_data_fetch.TWELVEDATA_ADAPTER_KEY, (
        "Trigger-only webhook must use the real candle adapter"
    )
    assert trigger_only_result["post_body"]["market_data_fetch"]["fetch_context"]["derived_higher_trend"] == "bullish", (
        "Trigger-only webhook must expose the derived higher timeframe trend"
    )
    assert trigger_only_result["post_body"]["automation"]["payload"]["decision"] == "BUY", (
        "Trigger-only webhook must route the fetched candles plus derived context into the BUY flow"
    )
    assert "AOI_VALID" in trigger_only_result["post_body"]["automation"]["payload"]["reason_codes"], (
        "Trigger-only webhook must preserve the explainable objective context in the final decision"
    )
    assert trigger_only_result["post_body"]["automation"]["run"]["paper_trade_created"] is True, (
        "Trigger-only webhook must create a paper trade when the derived trigger-only setup is actionable"
    )
    assert trigger_only_result["post_body"]["automation"]["run"]["trigger"] == "tradingview_trigger_only", (
        "Trigger-only webhook must preserve the dedicated trigger label"
    )

    print("PASS 4/4 tradingview webhook server scenarios")
    print("- valid_post_routes_into_buy_decision: status=200 decision=BUY paper_trade_created=True")
    print("- invalid_post_returns_422: status=422 validation_failed=True")
    print("- candle_bundle_post_routes_into_market_structure_buy: status=200 decision=BUY paper_trade_created=True")
    print("- trigger_only_post_fetches_real_candles_and_routes_into_buy: status=200 decision=BUY paper_trade_created=True")


if __name__ == "__main__":
    main()
