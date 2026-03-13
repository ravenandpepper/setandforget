import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import run_set_and_forget as engine
import run_structured_automation as automation
import tradingview_webhook


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_ROUTE = "/webhooks/tradingview"
DEFAULT_HEALTH_ROUTE = "/healthz"


def load_runtime_assets(
    *,
    webhook_schema_file: Path,
    skill_file: Path,
    decision_schema_file: Path,
):
    return {
        "webhook_schema": tradingview_webhook.load_json(webhook_schema_file),
        "skill": engine.load_json(skill_file),
        "decision_schema": engine.load_json(decision_schema_file),
    }


def build_server_config(
    *,
    route: str,
    health_route: str,
    paper_trades_log: Path,
    runs_dir: Path,
    decision_log: Path,
    assets: dict,
):
    return {
        "route": route,
        "health_route": health_route,
        "paper_trades_log": paper_trades_log,
        "runs_dir": runs_dir,
        "decision_log": decision_log,
        "assets": assets,
    }


def decode_json_body(raw_body: bytes):
    if not raw_body:
        raise ValueError("Request body is empty.")
    try:
        return json.loads(raw_body.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise ValueError("Request body must be valid UTF-8.") from error
    except json.JSONDecodeError as error:
        raise ValueError("Request body must be valid JSON.") from error


def process_webhook_request(raw_body: bytes, config: dict):
    try:
        payload = decode_json_body(raw_body)
    except ValueError as error:
        return {
            "status": "invalid_request",
            "validation": {
                "ok": False,
                "errors": [str(error)],
            },
            "automation": None,
        }, HTTPStatus.BAD_REQUEST

    result, exit_code = tradingview_webhook.run_tradingview_ingest(
        alert_payload=payload,
        webhook_schema=config["assets"]["webhook_schema"],
        skill=config["assets"]["skill"],
        decision_schema=config["assets"]["decision_schema"],
        runs_dir=config["runs_dir"],
        paper_trades_log=config["paper_trades_log"],
        decision_log=config["decision_log"],
    )
    if exit_code == 0:
        return result, HTTPStatus.OK
    return result, HTTPStatus.UNPROCESSABLE_ENTITY


def write_json_response(handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: dict):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status.value)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def build_handler(config: dict):
    class TradingViewWebhookHandler(BaseHTTPRequestHandler):
        server_version = "SetAndForgetTradingViewWebhook/1.0"

        def do_GET(self):
            if self.path != config["health_route"]:
                write_json_response(
                    self,
                    HTTPStatus.NOT_FOUND,
                    {
                        "status": "not_found",
                        "path": self.path,
                    },
                )
                return

            write_json_response(
                self,
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "tradingview_webhook_server",
                    "route": config["route"],
                },
            )

        def do_POST(self):
            if self.path != config["route"]:
                write_json_response(
                    self,
                    HTTPStatus.NOT_FOUND,
                    {
                        "status": "not_found",
                        "path": self.path,
                    },
                )
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            result, status = process_webhook_request(raw_body, config)
            write_json_response(self, status, result)

        def do_PUT(self):
            self._method_not_allowed()

        def do_DELETE(self):
            self._method_not_allowed()

        def _method_not_allowed(self):
            write_json_response(
                self,
                HTTPStatus.METHOD_NOT_ALLOWED,
                {
                    "status": "method_not_allowed",
                    "allowed_methods": ["GET", "POST"],
                },
            )

        def log_message(self, format, *args):
            return

    return TradingViewWebhookHandler


def serve(
    *,
    host: str,
    port: int,
    route: str,
    health_route: str,
    webhook_schema_file: Path,
    skill_file: Path,
    decision_schema_file: Path,
    paper_trades_log: Path,
    runs_dir: Path,
    decision_log: Path,
):
    assets = load_runtime_assets(
        webhook_schema_file=webhook_schema_file,
        skill_file=skill_file,
        decision_schema_file=decision_schema_file,
    )
    config = build_server_config(
        route=route,
        health_route=health_route,
        paper_trades_log=paper_trades_log,
        runs_dir=runs_dir,
        decision_log=decision_log,
        assets=assets,
    )
    server = ThreadingHTTPServer((host, port), build_handler(config))
    return server, config


def main():
    parser = argparse.ArgumentParser(description="Run a local TradingView webhook server for Set & Forget.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--route", default=DEFAULT_ROUTE)
    parser.add_argument("--health-route", default=DEFAULT_HEALTH_ROUTE)
    parser.add_argument("--webhook-schema-file", type=Path, default=tradingview_webhook.WEBHOOK_SCHEMA_FILE)
    parser.add_argument("--skill-file", type=Path, default=engine.SKILL_FILE)
    parser.add_argument("--decision-schema-file", type=Path, default=engine.DECISION_SCHEMA_FILE)
    parser.add_argument("--paper-trades-log", type=Path, default=engine.PAPER_TRADES_LOG_FILE)
    parser.add_argument("--runs-dir", type=Path, default=automation.AUTOMATION_RUNS_DIR)
    parser.add_argument("--decision-log", type=Path, default=automation.AUTOMATION_DECISIONS_LOG_FILE)
    args = parser.parse_args()

    server, _config = serve(
        host=args.host,
        port=args.port,
        route=args.route,
        health_route=args.health_route,
        webhook_schema_file=args.webhook_schema_file,
        skill_file=args.skill_file,
        decision_schema_file=args.decision_schema_file,
        paper_trades_log=args.paper_trades_log,
        runs_dir=args.runs_dir,
        decision_log=args.decision_log,
    )
    try:
        print(
            json.dumps(
                {
                    "status": "listening",
                    "host": args.host,
                    "port": args.port,
                    "route": args.route,
                    "health_route": args.health_route,
                },
                ensure_ascii=False,
            )
        )
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
