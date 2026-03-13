import json
import tempfile
from pathlib import Path

import run_market_structure_to_decision as runner


BASE_DIR = Path(__file__).resolve().parent
FIXTURES_FILE = BASE_DIR / "market_structure_test_fixtures.json"
INPUT_SCHEMA_FILE = BASE_DIR / "market_structure_input_schema.json"
FEATURE_SCHEMA_FILE = BASE_DIR / "feature_snapshot_schema.json"
DECISION_SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"
SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def run_case(case: dict, skill: dict, input_schema: dict, feature_schema: dict, decision_schema: dict):
    expected = case["expected"]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        result, exit_code = runner.run_market_structure_to_decision(
            market_input=case["market_input"],
            skill=skill,
            input_schema=input_schema,
            feature_schema=feature_schema,
            decision_schema=decision_schema,
            runs_dir=tmp_path / "automation_runs",
            paper_trades_log=tmp_path / "paper_trades_log.jsonl",
            decision_log=tmp_path / "automation_decisions_log.jsonl",
            trigger="test",
            run_label=case["id"],
        )

        assert exit_code == 0, f"{case['id']}: expected successful run"
        assert result["status"] == "ok", f"{case['id']}: result status should be ok"
        assert result["feature_snapshot"] is not None, f"{case['id']}: missing feature snapshot"
        assert result["projected_snapshot"] is not None, f"{case['id']}: missing projected snapshot"
        assert result["automation"]["payload"]["decision"] == expected["decision"], (
            f"{case['id']}: expected decision {expected['decision']}, got {result['automation']['payload']['decision']}"
        )

    return {
        "id": case["id"],
        "decision": result["automation"]["payload"]["decision"],
        "paper_trade_created": result["automation"]["run"]["paper_trade_created"],
    }


def run_invalid_case(skill: dict, input_schema: dict, feature_schema: dict, decision_schema: dict):
    invalid_input = {
        "meta": {
            "pair": "EURUSD",
            "execution_timeframe": "4H",
            "execution_mode": "paper",
            "source_kind": "invalid_fixture",
        },
        "candles": {},
        "objective_context": {},
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        result, exit_code = runner.run_market_structure_to_decision(
            market_input=invalid_input,
            skill=skill,
            input_schema=input_schema,
            feature_schema=feature_schema,
            decision_schema=decision_schema,
            runs_dir=tmp_path / "automation_runs",
            paper_trades_log=tmp_path / "paper_trades_log.jsonl",
            decision_log=tmp_path / "automation_decisions_log.jsonl",
            trigger="test",
            run_label="invalid_case",
        )

    assert exit_code == 1, "invalid case should fail with exit code 1"
    assert result["status"] == "error", "invalid case should return an error result"
    assert result["stage"] == "market_input_validation", "invalid case should fail at market input validation"
    assert result["errors"], "invalid case should report validation errors"
    return {"id": "invalid_market_input", "stage": result["stage"]}


def main():
    fixtures = load_json(FIXTURES_FILE)
    skill = load_json(SKILL_FILE)
    input_schema = load_json(INPUT_SCHEMA_FILE)
    feature_schema = load_json(FEATURE_SCHEMA_FILE)
    decision_schema = load_json(DECISION_SCHEMA_FILE)

    results = []
    for case in fixtures["cases"]:
        results.append(run_case(case, skill, input_schema, feature_schema, decision_schema))
    invalid = run_invalid_case(skill, input_schema, feature_schema, decision_schema)

    print(f"PASS {len(results) + 1}/{len(results) + 1} market structure to decision scenarios")
    for result in results:
        print(
            f"- {result['id']}: decision={result['decision']} "
            f"paper_trade_created={result['paper_trade_created']}"
        )
    print(f"- {invalid['id']}: stage={invalid['stage']}")


if __name__ == "__main__":
    main()
