import argparse
from pathlib import Path

import market_data_fetch_schedule
import runtime_status_artifact
import run_market_data_fetch_schedule_batch as batch_runner
import run_set_and_forget as engine
import run_structured_automation as automation
import tradingview_webhook


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = BASE_DIR / "scheduled_market_watch.json"
DEFAULT_RUNTIME_STATUS_FILE = BASE_DIR / "openclaw_runtime_status.json"


def load_runtime_config(path: Path):
    config = tradingview_webhook.load_json(path)
    pairs = config.get("pairs") or []
    if not isinstance(pairs, list) or not any(isinstance(item, str) and item.strip() for item in pairs):
        raise ValueError("scheduled market watch config requires at least one pair.")
    return {
        "pairs": market_data_fetch_schedule.normalize_pairs(
            [item for item in pairs if isinstance(item, str) and item.strip()]
        ),
        "execution_timeframe": config.get("execution_timeframe") or "4H",
        "execution_mode": config.get("execution_mode") or "paper",
        "max_requests_per_minute": int(config.get("max_requests_per_minute", 6)),
        "minute_spacing": int(config.get("minute_spacing", 1)),
        "fxalex_confluence_enabled": bool(config.get("fxalex_confluence_enabled", False)),
        "news_context_enabled": bool(config.get("news_context_enabled", False)),
    }


def run_scheduled_market_watch(
    config_file: Path,
    trigger_time: str | None,
    output_format: str,
    runs_dir: Path,
    paper_trades_log: Path,
    decision_log: Path,
    webhook_schema_file: Path,
    skill_file: Path,
    decision_schema_file: Path,
    enforce_run_guard: bool,
    runtime_status_file: Path,
    tournament_sidecar_config_file: Path,
):
    config = load_runtime_config(config_file)
    webhook_schema = tradingview_webhook.load_json(webhook_schema_file)
    skill = engine.load_json(skill_file)
    decision_schema = engine.load_json(decision_schema_file)
    summary, exit_code = batch_runner.run_scheduled_trigger_batch(
        pairs=config["pairs"],
        trigger_time=trigger_time,
        webhook_schema=webhook_schema,
        skill=skill,
        decision_schema=decision_schema,
        runs_dir=runs_dir,
        paper_trades_log=paper_trades_log,
        decision_log=decision_log,
        execution_timeframe=config["execution_timeframe"],
        execution_mode=config["execution_mode"],
        max_requests_per_minute=config["max_requests_per_minute"],
        minute_spacing=config["minute_spacing"],
        fxalex_confluence_enabled=config["fxalex_confluence_enabled"],
        news_context_enabled=config["news_context_enabled"],
        enforce_run_guard=enforce_run_guard,
        tournament_sidecar_config_file=tournament_sidecar_config_file,
    )
    if summary.get("status") == "skipped_by_guard":
        runtime_status_artifact.update_status(
            runtime_status_file,
            market_watch=runtime_status_artifact.build_market_watch_skipped_status(summary),
        )
    else:
        runtime_status_artifact.update_status(
            runtime_status_file,
            market_watch=runtime_status_artifact.build_market_watch_status(summary),
        )
    batch_runner.emit_output(summary, output_format)
    return summary, exit_code


def main():
    parser = argparse.ArgumentParser(description="Run the scheduled Set & Forget guarded paper-market watch.")
    parser.add_argument("--config-file", type=Path, default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--trigger-time", default=None, help="UTC trigger time in ISO-8601 form. Defaults to the current UTC minute.")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--webhook-schema-file", type=Path, default=tradingview_webhook.WEBHOOK_SCHEMA_FILE)
    parser.add_argument("--skill-file", type=Path, default=engine.SKILL_FILE)
    parser.add_argument("--decision-schema-file", type=Path, default=engine.DECISION_SCHEMA_FILE)
    parser.add_argument("--paper-trades-log", type=Path, default=engine.PAPER_TRADES_LOG_FILE)
    parser.add_argument("--runs-dir", type=Path, default=automation.AUTOMATION_RUNS_DIR)
    parser.add_argument("--decision-log", type=Path, default=automation.AUTOMATION_DECISIONS_LOG_FILE)
    parser.add_argument("--runtime-status-file", type=Path, default=DEFAULT_RUNTIME_STATUS_FILE)
    parser.add_argument("--tournament-sidecar-config-file", type=Path, default=tradingview_webhook.TOURNAMENT_SIDECAR_CONFIG_FILE)
    parser.add_argument("--disable-run-guard", action="store_true")
    args = parser.parse_args()

    _, exit_code = run_scheduled_market_watch(
        config_file=args.config_file,
        trigger_time=args.trigger_time,
        output_format=args.format,
        runs_dir=args.runs_dir,
        paper_trades_log=args.paper_trades_log,
        decision_log=args.decision_log,
        webhook_schema_file=args.webhook_schema_file,
        skill_file=args.skill_file,
        decision_schema_file=args.decision_schema_file,
        enforce_run_guard=not args.disable_run_guard,
        runtime_status_file=args.runtime_status_file,
        tournament_sidecar_config_file=args.tournament_sidecar_config_file,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
