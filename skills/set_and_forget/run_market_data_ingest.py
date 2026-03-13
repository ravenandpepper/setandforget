import argparse
import json
import sys
from pathlib import Path

import feature_snapshot
import market_data_ingest
import market_structure
import run_set_and_forget as engine
import run_structured_automation as automation


BASE_DIR = Path(__file__).resolve().parent


def emit_output(result: dict, output_format: str):
    if output_format == "text":
        lines = [
            "=" * 100,
            "SET AND FORGET MARKET DATA INGEST",
            f"Status: {result['status']}",
            f"Stage: {result['stage']}",
        ]
        market_input = result.get("market_input") or {}
        meta = market_input.get("meta", {})
        lines.append(f"Pair: {meta.get('pair')}")
        lines.append(f"Timeframe: {meta.get('execution_timeframe')}")
        if result.get("decision_run") and result["decision_run"].get("status") == "ok":
            run = result["decision_run"]["automation"]["run"]
            payload = result["decision_run"]["automation"]["payload"]
            lines.append(
                f"Decision: {payload['decision']} | confidence={payload['confidence_score']} | paper_trade={run['paper_trade_created']}"
            )
            lines.append(f"Run ID: {run['run_id']}")
        elif result.get("errors"):
            lines.append(f"Errors: {' | '.join(result['errors'])}")
        print("\n".join(lines))
        return

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()


def main():
    parser = argparse.ArgumentParser(description="Ingest candle bundles into the Set & Forget market structure runner.")
    parser.add_argument("--payload-file", type=Path, default=BASE_DIR / "market_data_ingest.example.json")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--ingest-schema-file", type=Path, default=market_data_ingest.INGEST_SCHEMA_FILE)
    parser.add_argument("--input-schema-file", type=Path, default=market_structure.MARKET_STRUCTURE_INPUT_SCHEMA_FILE)
    parser.add_argument("--feature-schema-file", type=Path, default=feature_snapshot.FEATURE_SNAPSHOT_SCHEMA_FILE)
    parser.add_argument("--skill-file", type=Path, default=engine.SKILL_FILE)
    parser.add_argument("--decision-schema-file", type=Path, default=engine.DECISION_SCHEMA_FILE)
    parser.add_argument("--paper-trades-log", type=Path, default=engine.PAPER_TRADES_LOG_FILE)
    parser.add_argument("--runs-dir", type=Path, default=automation.AUTOMATION_RUNS_DIR)
    parser.add_argument("--decision-log", type=Path, default=automation.AUTOMATION_DECISIONS_LOG_FILE)
    args = parser.parse_args()

    ingest_payload = market_data_ingest.load_json(args.payload_file)
    ingest_schema = market_data_ingest.load_json(args.ingest_schema_file)
    input_schema = market_structure.load_json(args.input_schema_file)
    feature_schema = feature_snapshot.load_json(args.feature_schema_file)
    skill = engine.load_json(args.skill_file)
    decision_schema = engine.load_json(args.decision_schema_file)

    result, exit_code = market_data_ingest.run_market_data_ingest(
        ingest_payload=ingest_payload,
        ingest_schema=ingest_schema,
        input_schema=input_schema,
        feature_schema=feature_schema,
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
