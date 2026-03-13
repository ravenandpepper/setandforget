import json
import tempfile
from pathlib import Path

import run_set_and_forget as engine
import tradingview_webhook


BASE_DIR = Path(__file__).resolve().parent
FIXTURES_FILE = BASE_DIR / "tradingview_webhook_test_fixtures.json"
WEBHOOK_SCHEMA_FILE = BASE_DIR / "tradingview_webhook_schema.json"
SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"
DECISION_SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"


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


def run_case(case: dict, webhook_schema: dict, skill: dict, decision_schema: dict):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        paper_trades_log = tmp_path / "paper_trades_log.jsonl"
        decision_log = tmp_path / "automation_decisions_log.jsonl"
        runs_dir = tmp_path / "automation_runs"

        result, exit_code = tradingview_webhook.run_tradingview_ingest(
            alert_payload=case["alert_payload"],
            webhook_schema=webhook_schema,
            skill=skill,
            decision_schema=decision_schema,
            runs_dir=runs_dir,
            paper_trades_log=paper_trades_log,
            decision_log=decision_log,
        )

        expected = case["expected"]
        assert exit_code == 0, f"{case['id']}: expected exit_code 0, got {exit_code}"
        assert result["status"] == "processed", f"{case['id']}: alert should be processed"
        assert result["alert_context"]["normalized_pair"] == expected["normalized_pair"], (
            f"{case['id']}: normalized pair mismatch"
        )
        assert result["alert_context"]["normalized_execution_timeframe"] == expected["normalized_execution_timeframe"], (
            f"{case['id']}: normalized timeframe mismatch"
        )
        assert result["snapshot"]["pair"] == expected["normalized_pair"], (
            f"{case['id']}: snapshot pair mismatch"
        )
        assert result["snapshot"]["execution_timeframe"] == expected["normalized_execution_timeframe"], (
            f"{case['id']}: snapshot timeframe mismatch"
        )
        assert result["automation"]["payload"]["decision"] == expected["decision"], (
            f"{case['id']}: decision mismatch"
        )

        decision_rows = load_jsonl(decision_log)
        paper_trade_rows = load_jsonl(paper_trades_log)
        assert len(decision_rows) == 1, f"{case['id']}: expected one automation decision row"
        assert decision_rows[0]["trigger"] == "tradingview_webhook", (
            f"{case['id']}: trigger should be tradingview_webhook"
        )
        assert decision_rows[0]["decision"] == expected["decision"], (
            f"{case['id']}: decision log mismatch"
        )
        assert decision_rows[0]["paper_trade_created"] == expected["paper_trade_created"], (
            f"{case['id']}: unexpected paper_trade_created value"
        )

        if expected["paper_trade_created"]:
            assert len(paper_trade_rows) == 1, f"{case['id']}: expected one paper trade row"
        else:
            assert len(paper_trade_rows) == 0, f"{case['id']}: unexpected paper trade row"

        validation_errors = engine.validate_snapshot(result["snapshot"], decision_schema)
        assert not validation_errors, f"{case['id']}: mapped snapshot is invalid: {validation_errors}"

        return {
            "id": case["id"],
            "decision": result["automation"]["payload"]["decision"],
            "paper_trade_created": expected["paper_trade_created"],
        }


def main():
    fixtures = load_json(FIXTURES_FILE)
    webhook_schema = load_json(WEBHOOK_SCHEMA_FILE)
    skill = load_json(SKILL_FILE)
    decision_schema = load_json(DECISION_SCHEMA_FILE)

    results = []
    for case in fixtures["cases"]:
        results.append(run_case(case, webhook_schema, skill, decision_schema))

    print(f"PASS {len(results)}/{len(fixtures['cases'])} tradingview webhook scenarios")
    for result in results:
        print(
            f"- {result['id']}: decision={result['decision']} "
            f"paper_trade_created={result['paper_trade_created']}"
        )


if __name__ == "__main__":
    main()
