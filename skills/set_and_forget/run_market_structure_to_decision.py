import argparse
import json
import sys
from pathlib import Path

import feature_snapshot
import live_tournament_sidecar
import market_structure
import run_set_and_forget as engine
import run_structured_automation as automation


BASE_DIR = Path(__file__).resolve().parent
INPUT_SCHEMA_FILE = BASE_DIR / "market_structure_input_schema.json"
FEATURE_SCHEMA_FILE = BASE_DIR / "feature_snapshot_schema.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def build_stage_error_result(stage: str, errors: list[str], market_input: dict):
    meta = market_input.get("meta", {})
    return {
        "status": "error",
        "stage": stage,
        "errors": errors,
        "pair": meta.get("pair", "UNKNOWN"),
        "execution_timeframe": meta.get("execution_timeframe", "UNKNOWN"),
        "execution_mode": meta.get("execution_mode", "paper"),
        "feature_snapshot": None,
        "projected_snapshot": None,
        "automation": None,
        "tournament": None,
    }


def run_market_structure_to_decision(
    market_input: dict,
    skill: dict,
    input_schema: dict,
    feature_schema: dict,
    decision_schema: dict,
    runs_dir: Path,
    paper_trades_log: Path,
    decision_log: Path,
    trigger: str = "market_structure",
    run_label: str | None = None,
    tournament_sidecar_config_file: Path | None = None,
):
    input_errors = market_structure.validate_market_structure_input(market_input, input_schema)
    if input_errors:
        return build_stage_error_result("market_input_validation", input_errors, market_input), 1

    feature_payload = market_structure.build_feature_snapshot_from_market_input(market_input)
    feature_errors = feature_snapshot.validate_feature_snapshot(feature_payload, feature_schema)
    if feature_errors:
        return build_stage_error_result("feature_snapshot_validation", feature_errors, market_input), 1

    projected_snapshot = feature_snapshot.project_to_decision_snapshot(feature_payload)
    snapshot_errors = engine.validate_snapshot(projected_snapshot, decision_schema)
    if snapshot_errors:
        return build_stage_error_result("decision_snapshot_validation", snapshot_errors, market_input), 1

    automation_result, exit_code = automation.run_structured_automation(
        snapshot=projected_snapshot,
        skill=skill,
        schema=decision_schema,
        runs_dir=runs_dir,
        paper_trades_log=paper_trades_log,
        decision_log=decision_log,
        trigger=trigger,
        run_label=run_label or market_input.get("meta", {}).get("source_kind"),
    )
    tournament_result = None
    if exit_code == 0 and tournament_sidecar_config_file is not None:
        tournament_result, _tournament_exit_code = live_tournament_sidecar.run_live_tournament_sidecar(
            feature_snapshot=feature_payload,
            skill=skill,
            decision_schema=decision_schema,
            config_file=tournament_sidecar_config_file,
        )
    return {
        "status": "ok",
        "stage": "decision_complete",
        "errors": [],
        "feature_snapshot": feature_payload,
        "projected_snapshot": projected_snapshot,
        "automation": automation_result,
        "tournament": tournament_result,
    }, exit_code


def emit_output(result: dict, output_format: str):
    if output_format == "text":
        if result["status"] != "ok":
            lines = [
                "=" * 100,
                "SET AND FORGET MARKET STRUCTURE RUN",
                f"Status: {result['status']}",
                f"Stage: {result['stage']}",
                f"Pair: {result['pair']}",
                f"Execution timeframe: {result['execution_timeframe']}",
                f"Errors: {' | '.join(result['errors'])}",
            ]
            print("\n".join(lines))
            return

        run = result["automation"]["run"]
        payload = result["automation"]["payload"]
        lines = [
            "=" * 100,
            "SET AND FORGET MARKET STRUCTURE TO DECISION",
            f"Decision: {payload['decision']} | confidence={payload['confidence_score']}",
            f"Pair: {payload['pair']} | timeframe={payload['execution_timeframe']}",
            f"Run ID: {run['run_id']}",
            f"Trigger: {run['trigger']}",
            f"Decision file: {run['decision_path']}",
            f"Paper trade created: {run['paper_trade_created']}",
        ]
        print("\n".join(lines))
        return

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()


def main():
    parser = argparse.ArgumentParser(description="Run Set & Forget from raw market structure candles to final decision.")
    parser.add_argument("--market-input-file", type=Path, required=True)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--skill-file", type=Path, default=engine.SKILL_FILE)
    parser.add_argument("--input-schema-file", type=Path, default=INPUT_SCHEMA_FILE)
    parser.add_argument("--feature-schema-file", type=Path, default=FEATURE_SCHEMA_FILE)
    parser.add_argument("--decision-schema-file", type=Path, default=engine.DECISION_SCHEMA_FILE)
    parser.add_argument("--paper-trades-log", type=Path, default=engine.PAPER_TRADES_LOG_FILE)
    parser.add_argument("--runs-dir", type=Path, default=automation.AUTOMATION_RUNS_DIR)
    parser.add_argument("--decision-log", type=Path, default=automation.AUTOMATION_DECISIONS_LOG_FILE)
    parser.add_argument("--trigger", default="market_structure")
    parser.add_argument("--run-label", default=None)
    parser.add_argument("--tournament-sidecar-config-file", type=Path, default=None)
    args = parser.parse_args()

    market_input = load_json(args.market_input_file)
    skill = load_json(args.skill_file)
    input_schema = load_json(args.input_schema_file)
    feature_schema = load_json(args.feature_schema_file)
    decision_schema = load_json(args.decision_schema_file)

    result, exit_code = run_market_structure_to_decision(
        market_input=market_input,
        skill=skill,
        input_schema=input_schema,
        feature_schema=feature_schema,
        decision_schema=decision_schema,
        runs_dir=args.runs_dir,
        paper_trades_log=args.paper_trades_log,
        decision_log=args.decision_log,
        trigger=args.trigger,
        run_label=args.run_label,
        tournament_sidecar_config_file=args.tournament_sidecar_config_file,
    )
    emit_output(result, args.format)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
