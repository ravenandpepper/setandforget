import http.client
import json
import tempfile
import threading
from pathlib import Path

import run_set_and_forget as engine
import run_structured_automation as automation
import tradingview_webhook
import tradingview_webhook_server as server_module


BASE_DIR = Path(__file__).resolve().parent
ALERT_FILE = BASE_DIR / "tradingview_alert.example.json"


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


def run_server_case(alert_payload: dict):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        paper_trades_log = tmp_path / "paper_trades_log.jsonl"
        decision_log = tmp_path / "automation_decisions_log.jsonl"
        runs_dir = tmp_path / "automation_runs"

        server, config = server_module.serve(
            host="127.0.0.1",
            port=0,
            route=server_module.DEFAULT_ROUTE,
            health_route=server_module.DEFAULT_HEALTH_ROUTE,
            webhook_schema_file=tradingview_webhook.WEBHOOK_SCHEMA_FILE,
            skill_file=engine.SKILL_FILE,
            decision_schema_file=engine.DECISION_SCHEMA_FILE,
            paper_trades_log=paper_trades_log,
            runs_dir=runs_dir,
            decision_log=decision_log,
        )
        host, port = server.server_address
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            health_status, health_body = request_json("GET", host, port, config["health_route"])
            post_status, post_body = request_json("POST", host, port, config["route"], alert_payload)
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
    result = run_server_case(bullish_alert)

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

    invalid_result = run_server_case({"source": "tradingview"})
    assert invalid_result["post_status"] == 422, "Invalid TradingView payload must return 422"
    assert invalid_result["post_body"]["status"] in {"invalid_alert", "invalid_snapshot"}, (
        "Invalid TradingView payload must fail validation"
    )

    print("PASS 2/2 tradingview webhook server scenarios")
    print("- valid_post_routes_into_buy_decision: status=200 decision=BUY paper_trade_created=True")
    print("- invalid_post_returns_422: status=422 validation_failed=True")


if __name__ == "__main__":
    main()
