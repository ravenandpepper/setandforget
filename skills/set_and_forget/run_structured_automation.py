import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import run_set_and_forget as engine

BASE_DIR = Path(__file__).resolve().parent
AUTOMATION_RUNS_DIR = BASE_DIR / "automation_runs"
AUTOMATION_DECISIONS_LOG_FILE = BASE_DIR / "automation_decisions_log.jsonl"


def dump_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def append_jsonl(path: Path, row: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False))
        handle.write("\n")


def slugify(value: str):
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    return cleaned.strip("_").lower() or "unknown"


def build_run_id(snapshot: dict, run_label: str | None):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    parts = [
        timestamp,
        slugify(run_label or "scheduled"),
        slugify(snapshot.get("pair", "unknown")),
        slugify(snapshot.get("execution_timeframe", "unknown")),
    ]
    return "_".join(parts)


def build_run_record(
    run_id: str,
    trigger: str,
    snapshot_path: Path,
    decision_path: Path,
    decision_log_path: Path,
    payload: dict,
    exit_code: int,
    paper_trade_ticket_path: Path | None,
):
    paper_trade_state = payload.get("paper_trade", {})
    return {
        "run_id": run_id,
        "trigger": trigger,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if exit_code == 0 else "error",
        "decision": payload["decision"],
        "confidence_score": payload["confidence_score"],
        "pair": payload.get("pair", "UNKNOWN"),
        "execution_timeframe": payload.get("execution_timeframe", "UNKNOWN"),
        "summary": payload["summary"],
        "reason_codes": payload["reason_codes"],
        "snapshot_path": str(snapshot_path),
        "decision_path": str(decision_path),
        "decision_log_path": str(decision_log_path),
        "paper_trade_created": bool(paper_trade_state.get("created", False)),
        "paper_trade_log_path": paper_trade_state.get("log_path"),
        "paper_trade_ticket_path": str(paper_trade_ticket_path) if paper_trade_ticket_path else None,
    }


def run_structured_automation(
    snapshot: dict,
    skill: dict,
    schema: dict,
    runs_dir: Path,
    paper_trades_log: Path,
    decision_log: Path,
    trigger: str = "scheduler",
    run_label: str | None = None,
):
    run_id = build_run_id(snapshot, run_label)
    run_dir = runs_dir / run_id
    snapshot_path = run_dir / "snapshot_in.json"
    decision_path = run_dir / "decision.json"
    paper_trade_ticket_path = run_dir / "paper_trade_ticket.json"

    dump_json(snapshot_path, snapshot)
    payload, exit_code = engine.run_decision_cycle(snapshot, skill, schema, paper_trades_log)
    dump_json(decision_path, payload)

    if payload.get("paper_trade", {}).get("created"):
        dump_json(paper_trade_ticket_path, payload["paper_trade"]["ticket"])
    else:
        paper_trade_ticket_path = None

    record = build_run_record(
        run_id=run_id,
        trigger=trigger,
        snapshot_path=snapshot_path,
        decision_path=decision_path,
        decision_log_path=decision_log,
        payload=payload,
        exit_code=exit_code,
        paper_trade_ticket_path=paper_trade_ticket_path,
    )
    append_jsonl(decision_log, record)

    return {
        "run": record,
        "payload": payload,
    }, exit_code


def emit_output(result: dict, output_format: str):
    if output_format == "text":
        run = result["run"]
        lines = [
            "=" * 100,
            "SET AND FORGET STRUCTURED AUTOMATION RUN",
            f"Run ID: {run['run_id']}",
            f"Trigger: {run['trigger']}",
            f"Decision: {run['decision']} | confidence={run['confidence_score']} | status={run['status']}",
            f"Snapshot: {run['snapshot_path']}",
            f"Decision file: {run['decision_path']}",
            f"Paper trade ticket: {run['paper_trade_ticket_path']}",
            f"Decision log: {run['decision_log_path']}",
        ]
        print("\n".join(lines))
        return

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()


def main():
    parser = argparse.ArgumentParser(description="Run structured automation around the Set & Forget engine.")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--skill-file", type=Path, default=engine.SKILL_FILE)
    parser.add_argument("--schema-file", type=Path, default=engine.DECISION_SCHEMA_FILE)
    parser.add_argument("--snapshot-file", type=Path, default=engine.LIVE_SNAPSHOT_FILE)
    parser.add_argument("--paper-trades-log", type=Path, default=engine.PAPER_TRADES_LOG_FILE)
    parser.add_argument("--runs-dir", type=Path, default=AUTOMATION_RUNS_DIR)
    parser.add_argument("--decision-log", type=Path, default=AUTOMATION_DECISIONS_LOG_FILE)
    parser.add_argument("--trigger", default="scheduler")
    parser.add_argument("--run-label", default=None)
    args = parser.parse_args()

    skill = engine.load_json(args.skill_file)
    schema = engine.load_json(args.schema_file)
    snapshot = engine.load_json(args.snapshot_file)

    result, exit_code = run_structured_automation(
        snapshot=snapshot,
        skill=skill,
        schema=schema,
        runs_dir=args.runs_dir,
        paper_trades_log=args.paper_trades_log,
        decision_log=args.decision_log,
        trigger=args.trigger,
        run_label=args.run_label,
    )
    emit_output(result, args.format)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
