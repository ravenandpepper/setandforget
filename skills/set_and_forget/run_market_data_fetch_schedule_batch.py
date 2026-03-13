import argparse
import json
import sys
from pathlib import Path

import market_data_fetch_schedule
import run_set_and_forget as engine
import run_structured_automation as automation
import tradingview_webhook


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TRIGGER_SOURCE = "tradingview"
DEFAULT_TRIGGER_KIND = "trigger_only"


def build_trigger_only_alert(trigger_request: dict, alert_name: str | None = None):
    pair = trigger_request["pair"]
    return {
        "source": DEFAULT_TRIGGER_SOURCE,
        "message_version": "tv_webhook_v1",
        "payload_kind": DEFAULT_TRIGGER_KIND,
        "pair": pair,
        "ticker": pair,
        "execution_timeframe": trigger_request["execution_timeframe"],
        "execution_mode": trigger_request["execution_mode"],
        "fxalex_confluence_enabled": trigger_request.get("fxalex_confluence_enabled", False),
        "news_context_enabled": trigger_request.get("news_context_enabled", False),
        "trigger_time": trigger_request["trigger_time"],
        "alert_name": alert_name or f"scheduled_trigger_only_{pair}",
    }


def build_run_summary(trigger_request: dict, result: dict, exit_code: int):
    automation_result = result.get("automation") or {}
    payload = automation_result.get("payload") or {}
    run = automation_result.get("run") or {}
    fetch_result = result.get("market_data_fetch") or {}
    fetch_context = fetch_result.get("fetch_context") or {}
    return {
        "pair": trigger_request["pair"],
        "trigger_time": trigger_request["trigger_time"],
        "exit_code": exit_code,
        "status": result.get("status"),
        "provider": fetch_context.get("provider"),
        "provider_symbol": fetch_context.get("provider_symbol"),
        "decision": payload.get("decision"),
        "confidence_score": payload.get("confidence_score"),
        "reason_codes": payload.get("reason_codes"),
        "summary": payload.get("summary"),
        "paper_trade_created": run.get("paper_trade_created", False),
        "validation_errors": (result.get("validation") or {}).get("errors", []),
    }


def run_schedule_plan(
    plan: dict,
    webhook_schema: dict,
    skill: dict,
    decision_schema: dict,
    runs_dir: Path,
    paper_trades_log: Path,
    decision_log: Path,
):
    bucket_results = []
    exit_code = 0
    total_runs = 0

    for bucket in plan["schedule"]["buckets"]:
        run_results = []
        bucket_exit_code = 0
        for trigger_request in bucket["trigger_requests"]:
            alert_payload = build_trigger_only_alert(trigger_request)
            result, run_exit_code = tradingview_webhook.run_tradingview_ingest(
                alert_payload=alert_payload,
                webhook_schema=webhook_schema,
                skill=skill,
                decision_schema=decision_schema,
                runs_dir=runs_dir,
                paper_trades_log=paper_trades_log,
                decision_log=decision_log,
            )
            run_results.append(build_run_summary(trigger_request, result, run_exit_code))
            total_runs += 1
            bucket_exit_code = max(bucket_exit_code, run_exit_code)
            exit_code = max(exit_code, run_exit_code)

        bucket_results.append(
            {
                "bucket_index": bucket["bucket_index"],
                "scheduled_for": bucket["scheduled_for"],
                "estimated_requests": bucket["estimated_requests"],
                "pairs": bucket["pairs"],
                "exit_code": bucket_exit_code,
                "runs": run_results,
            }
        )

    ok_runs = sum(1 for bucket in bucket_results for run in bucket["runs"] if run["exit_code"] == 0)
    error_runs = total_runs - ok_runs
    return {
        "provider": plan["provider"],
        "adapter": plan["adapter"],
        "execution_timeframe": plan["execution_timeframe"],
        "execution_mode": plan["execution_mode"],
        "request_budget": plan["request_budget"],
        "schedule": {
            **plan["schedule"],
            "buckets": bucket_results,
        },
        "total_runs": total_runs,
        "ok_runs": ok_runs,
        "error_runs": error_runs,
        "exit_code": exit_code,
    }, exit_code


def run_scheduled_trigger_batch(
    pairs: list[str],
    trigger_time: str | None,
    webhook_schema: dict,
    skill: dict,
    decision_schema: dict,
    runs_dir: Path,
    paper_trades_log: Path,
    decision_log: Path,
    execution_timeframe: str = market_data_fetch_schedule.DEFAULT_EXECUTION_TIMEFRAME,
    execution_mode: str = market_data_fetch_schedule.DEFAULT_EXECUTION_MODE,
    max_requests_per_minute: int = market_data_fetch_schedule.DEFAULT_MAX_REQUESTS_PER_MINUTE,
    minute_spacing: int = market_data_fetch_schedule.DEFAULT_MINUTE_SPACING,
    fxalex_confluence_enabled: bool = False,
    news_context_enabled: bool = False,
):
    plan = market_data_fetch_schedule.build_fetch_schedule(
        pairs=pairs,
        trigger_time=trigger_time,
        execution_timeframe=execution_timeframe,
        execution_mode=execution_mode,
        max_requests_per_minute=max_requests_per_minute,
        minute_spacing=minute_spacing,
        fxalex_confluence_enabled=fxalex_confluence_enabled,
        news_context_enabled=news_context_enabled,
    )
    return run_schedule_plan(
        plan=plan,
        webhook_schema=webhook_schema,
        skill=skill,
        decision_schema=decision_schema,
        runs_dir=runs_dir,
        paper_trades_log=paper_trades_log,
        decision_log=decision_log,
    )


def emit_output(summary: dict, output_format: str):
    if output_format == "json":
        json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return

    lines = [
        "=" * 100,
        "MARKET DATA FETCH SCHEDULE BATCH",
        (
            f"Provider: {summary['provider']} | adapter={summary['adapter']} "
            f"| timeframe={summary['execution_timeframe']} | mode={summary['execution_mode']}"
        ),
        (
            f"Runs: total={summary['total_runs']} ok={summary['ok_runs']} error={summary['error_runs']} "
            f"| exit_code={summary['exit_code']}"
        ),
    ]
    for bucket in summary["schedule"]["buckets"]:
        lines.append(
            f"- {bucket['scheduled_for']}: pairs={','.join(bucket['pairs'])} "
            f"estimated_requests={bucket['estimated_requests']} exit_code={bucket['exit_code']}"
        )
        for run in bucket["runs"]:
            lines.append(
                f"  {run['pair']}: decision={run['decision']} confidence={run['confidence_score']} "
                f"paper_trade={run['paper_trade_created']}"
            )
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Run a minute-bucketed trigger-only batch through the existing market-data pipeline.")
    parser.add_argument("--pairs", required=True, help="Comma-separated list of forex pairs, for example EURUSD,GBPUSD,USDJPY")
    parser.add_argument("--trigger-time", default=None, help="Base UTC trigger time in ISO-8601 form. Defaults to the current UTC minute.")
    parser.add_argument("--execution-timeframe", default=market_data_fetch_schedule.DEFAULT_EXECUTION_TIMEFRAME)
    parser.add_argument("--execution-mode", default=market_data_fetch_schedule.DEFAULT_EXECUTION_MODE)
    parser.add_argument("--max-requests-per-minute", type=int, default=market_data_fetch_schedule.DEFAULT_MAX_REQUESTS_PER_MINUTE)
    parser.add_argument("--minute-spacing", type=int, default=market_data_fetch_schedule.DEFAULT_MINUTE_SPACING)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--webhook-schema-file", type=Path, default=tradingview_webhook.WEBHOOK_SCHEMA_FILE)
    parser.add_argument("--skill-file", type=Path, default=engine.SKILL_FILE)
    parser.add_argument("--decision-schema-file", type=Path, default=engine.DECISION_SCHEMA_FILE)
    parser.add_argument("--paper-trades-log", type=Path, default=engine.PAPER_TRADES_LOG_FILE)
    parser.add_argument("--runs-dir", type=Path, default=automation.AUTOMATION_RUNS_DIR)
    parser.add_argument("--decision-log", type=Path, default=automation.AUTOMATION_DECISIONS_LOG_FILE)
    args = parser.parse_args()

    webhook_schema = tradingview_webhook.load_json(args.webhook_schema_file)
    skill = engine.load_json(args.skill_file)
    decision_schema = engine.load_json(args.decision_schema_file)
    summary, exit_code = run_scheduled_trigger_batch(
        pairs=[item.strip() for item in args.pairs.split(",") if item.strip()],
        trigger_time=args.trigger_time,
        webhook_schema=webhook_schema,
        skill=skill,
        decision_schema=decision_schema,
        runs_dir=args.runs_dir,
        paper_trades_log=args.paper_trades_log,
        decision_log=args.decision_log,
        execution_timeframe=args.execution_timeframe,
        execution_mode=args.execution_mode,
        max_requests_per_minute=args.max_requests_per_minute,
        minute_spacing=args.minute_spacing,
    )
    emit_output(summary, args.format)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
