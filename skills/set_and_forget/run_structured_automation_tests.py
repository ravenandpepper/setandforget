import json
import tempfile
from pathlib import Path

import run_set_and_forget as engine
import run_structured_automation as automation

BASE_DIR = Path(__file__).resolve().parent
FIXTURES_FILE = BASE_DIR / "structured_automation_test_fixtures.json"
SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"
SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def run_case(case: dict, skill: dict, schema: dict):
    snapshot = case["snapshot"]
    expected = case["expected"]
    validation_errors = engine.validate_snapshot(snapshot, schema)
    assert not validation_errors, f"{case['id']}: invalid fixture: {validation_errors}"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        runs_dir = tmp_path / "automation_runs"
        paper_trades_log = tmp_path / "paper_trades_log.jsonl"
        decision_log = tmp_path / "automation_decisions_log.jsonl"

        result, exit_code = automation.run_structured_automation(
            snapshot=snapshot,
            skill=skill,
            schema=schema,
            runs_dir=runs_dir,
            paper_trades_log=paper_trades_log,
            decision_log=decision_log,
            trigger="test",
            run_label=case["id"],
        )

        run_record = result["run"]
        decision_payload = result["payload"]
        snapshot_file = Path(run_record["snapshot_path"])
        decision_file = Path(run_record["decision_path"])
        ticket_file = Path(run_record["paper_trade_ticket_path"]) if run_record["paper_trade_ticket_path"] else None
        decision_rows = load_jsonl(decision_log)
        paper_trade_rows = load_jsonl(paper_trades_log)
        assert exit_code == expected["exit_code"], (
            f"{case['id']}: expected exit_code {expected['exit_code']}, got {exit_code}"
        )
        assert decision_payload["decision"] == expected["decision"], (
            f"{case['id']}: expected decision {expected['decision']}, got {decision_payload['decision']}"
        )
        assert snapshot_file.exists(), f"{case['id']}: snapshot_in.json missing"
        assert decision_file.exists(), f"{case['id']}: decision.json missing"
        assert len(decision_rows) == 1, f"{case['id']}: expected one decision log row"
        assert decision_rows[0]["run_id"] == run_record["run_id"], f"{case['id']}: run_id mismatch in decision log"
        assert decision_rows[0]["paper_trade_created"] == expected["paper_trade_created"], (
            f"{case['id']}: unexpected paper_trade_created in decision log"
        )

        if expected["paper_trade_created"]:
            assert ticket_file is not None and ticket_file.exists(), f"{case['id']}: paper trade ticket missing"
            assert len(paper_trade_rows) == 1, f"{case['id']}: expected one paper trade row"
        else:
            assert ticket_file is None, f"{case['id']}: unexpected paper trade ticket file"
            assert len(paper_trade_rows) == 0, f"{case['id']}: unexpected paper trade log row"

    return {
        "id": case["id"],
        "decision": decision_payload["decision"],
        "paper_trade_created": expected["paper_trade_created"],
    }


def main():
    fixtures = load_json(FIXTURES_FILE)
    skill = load_json(SKILL_FILE)
    schema = load_json(SCHEMA_FILE)

    results = []
    for case in fixtures["cases"]:
        results.append(run_case(case, skill, schema))

    print(f"PASS {len(results)}/{len(fixtures['cases'])} structured automation scenarios")
    for result in results:
        print(
            f"- {result['id']}: decision={result['decision']} "
            f"paper_trade_created={result['paper_trade_created']}"
        )


if __name__ == "__main__":
    main()
