import argparse
import json
import sys
from pathlib import Path

import run_set_and_forget as engine
import run_structured_automation as automation
import tradingview_webhook


BASE_DIR = Path(__file__).resolve().parent


def emit_output(result: dict, output_format: str):
    if output_format == "text":
        lines = [
            "=" * 100,
            "TRADINGVIEW WEBHOOK INGEST",
            f"Status: {result['status']}",
            f"Pair: {result['alert_context'].get('normalized_pair')}",
            f"Timeframe: {result['alert_context'].get('normalized_execution_timeframe')}",
            f"Alert name: {result['alert_context'].get('alert_name')}",
        ]
        if result["automation"]:
            run = result["automation"]["run"]
            lines.append(
                f"Decision: {run['decision']} | confidence={run['confidence_score']} | paper_trade={run['paper_trade_created']}"
            )
            lines.append(f"Run ID: {run['run_id']}")
        else:
            lines.append("Decision: not processed")
        print("\n".join(lines))
        return

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()


def main():
    parser = argparse.ArgumentParser(description="Ingest a TradingView alert into the Set & Forget engine.")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--alert-file", type=Path, default=BASE_DIR / "tradingview_alert.example.json")
    parser.add_argument("--webhook-schema-file", type=Path, default=tradingview_webhook.WEBHOOK_SCHEMA_FILE)
    parser.add_argument("--skill-file", type=Path, default=engine.SKILL_FILE)
    parser.add_argument("--decision-schema-file", type=Path, default=engine.DECISION_SCHEMA_FILE)
    parser.add_argument("--paper-trades-log", type=Path, default=engine.PAPER_TRADES_LOG_FILE)
    parser.add_argument("--runs-dir", type=Path, default=automation.AUTOMATION_RUNS_DIR)
    parser.add_argument("--decision-log", type=Path, default=automation.AUTOMATION_DECISIONS_LOG_FILE)
    args = parser.parse_args()

    alert_payload = tradingview_webhook.load_json(args.alert_file)
    webhook_schema = tradingview_webhook.load_json(args.webhook_schema_file)
    skill = engine.load_json(args.skill_file)
    decision_schema = engine.load_json(args.decision_schema_file)

    result, exit_code = tradingview_webhook.run_tradingview_ingest(
        alert_payload=alert_payload,
        webhook_schema=webhook_schema,
        skill=skill,
        decision_schema=decision_schema,
        runs_dir=args.runs_dir,
        paper_trades_log=args.paper_trades_log,
        decision_log=args.decision_log,
    )
    emit_output(result, args.format)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
