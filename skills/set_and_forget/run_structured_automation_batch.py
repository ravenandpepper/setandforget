import argparse
import json
import sys
from pathlib import Path

import run_set_and_forget as engine
import run_structured_automation as automation

BASE_DIR = Path(__file__).resolve().parent


def resolve_snapshot_path(manifest_file: Path, snapshot_file: str):
    snapshot_path = Path(snapshot_file)
    if snapshot_path.is_absolute():
        return snapshot_path
    return (manifest_file.parent / snapshot_path).resolve()


def load_manifest(path: Path):
    manifest = engine.load_json(path)
    runs = manifest.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("Manifest must contain a non-empty 'runs' list.")

    for index, run in enumerate(runs, start=1):
        if not isinstance(run, dict):
            raise ValueError(f"Manifest run #{index} must be an object.")
        if "snapshot_file" not in run:
            raise ValueError(f"Manifest run #{index} is missing 'snapshot_file'.")

    return manifest


def build_batch_summary(manifest_file: Path, trigger: str, results: list, exit_code: int):
    return {
        "manifest_file": str(manifest_file),
        "trigger": trigger,
        "total_runs": len(results),
        "ok_runs": sum(1 for item in results if item["exit_code"] == 0),
        "error_runs": sum(1 for item in results if item["exit_code"] != 0),
        "exit_code": exit_code,
        "runs": results,
    }


def run_batch_from_manifest(
    manifest_file: Path,
    skill: dict,
    schema: dict,
    runs_dir: Path,
    paper_trades_log: Path,
    decision_log: Path,
    trigger: str = "scheduler_batch",
):
    manifest = load_manifest(manifest_file)
    results = []
    exit_code = 0

    for run in manifest["runs"]:
        snapshot_path = resolve_snapshot_path(manifest_file, run["snapshot_file"])
        snapshot = engine.load_json(snapshot_path)
        run_result, run_exit_code = automation.run_structured_automation(
            snapshot=snapshot,
            skill=skill,
            schema=schema,
            runs_dir=runs_dir,
            paper_trades_log=paper_trades_log,
            decision_log=decision_log,
            trigger=run.get("trigger", trigger),
            run_label=run.get("run_label"),
        )
        results.append(
            {
                "snapshot_file": str(snapshot_path),
                "run_label": run.get("run_label"),
                "exit_code": run_exit_code,
                "run_id": run_result["run"]["run_id"],
                "decision": run_result["run"]["decision"],
                "paper_trade_created": run_result["run"]["paper_trade_created"],
                "decision_path": run_result["run"]["decision_path"],
            }
        )
        exit_code = max(exit_code, run_exit_code)

    return build_batch_summary(manifest_file, trigger, results, exit_code), exit_code


def emit_output(summary: dict, output_format: str):
    if output_format == "text":
        lines = [
            "=" * 100,
            "SET AND FORGET STRUCTURED AUTOMATION BATCH",
            f"Manifest: {summary['manifest_file']}",
            f"Trigger: {summary['trigger']}",
            f"Runs: total={summary['total_runs']} ok={summary['ok_runs']} error={summary['error_runs']}",
        ]
        for item in summary["runs"]:
            lines.append(
                f"- {item['run_label'] or item['snapshot_file']}: "
                f"decision={item['decision']} exit_code={item['exit_code']} "
                f"paper_trade_created={item['paper_trade_created']}"
            )
        print("\n".join(lines))
        return

    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    print()


def main():
    parser = argparse.ArgumentParser(description="Run structured automation for multiple snapshots from a manifest.")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--skill-file", type=Path, default=engine.SKILL_FILE)
    parser.add_argument("--schema-file", type=Path, default=engine.DECISION_SCHEMA_FILE)
    parser.add_argument("--manifest-file", type=Path, required=True)
    parser.add_argument("--paper-trades-log", type=Path, default=engine.PAPER_TRADES_LOG_FILE)
    parser.add_argument("--runs-dir", type=Path, default=automation.AUTOMATION_RUNS_DIR)
    parser.add_argument("--decision-log", type=Path, default=automation.AUTOMATION_DECISIONS_LOG_FILE)
    parser.add_argument("--trigger", default="scheduler_batch")
    args = parser.parse_args()

    skill = engine.load_json(args.skill_file)
    schema = engine.load_json(args.schema_file)
    summary, exit_code = run_batch_from_manifest(
        manifest_file=args.manifest_file.resolve(),
        skill=skill,
        schema=schema,
        runs_dir=args.runs_dir,
        paper_trades_log=args.paper_trades_log,
        decision_log=args.decision_log,
        trigger=args.trigger,
    )
    emit_output(summary, args.format)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
