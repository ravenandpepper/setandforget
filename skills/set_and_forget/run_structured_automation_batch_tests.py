import json
import tempfile
from pathlib import Path

import run_set_and_forget as engine
import run_structured_automation_batch as batch_runner

BASE_DIR = Path(__file__).resolve().parent
FIXTURES_FILE = BASE_DIR / "structured_automation_batch_test_fixtures.json"
SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"
SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main():
    fixtures = load_json(FIXTURES_FILE)
    skill = load_json(SKILL_FILE)
    schema = load_json(SCHEMA_FILE)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        manifest_file = tmp_path / "manifest.json"
        snapshots_dir = tmp_path / "snapshots"
        runs_dir = tmp_path / "automation_runs"
        paper_trades_log = tmp_path / "paper_trades_log.jsonl"
        decision_log = tmp_path / "automation_decisions_log.jsonl"

        manifest = {"runs": []}
        expected_by_label = {}
        for fixture in fixtures["runs"]:
            snapshot_path = snapshots_dir / fixture["snapshot_name"]
            validation_errors = engine.validate_snapshot(fixture["snapshot"], schema)
            assert not validation_errors, f"{fixture['run_label']}: invalid fixture {validation_errors}"
            dump_json(snapshot_path, fixture["snapshot"])
            manifest["runs"].append(
                {
                    "snapshot_file": f"snapshots/{fixture['snapshot_name']}",
                    "run_label": fixture["run_label"],
                }
            )
            expected_by_label[fixture["run_label"]] = fixture

        dump_json(manifest_file, manifest)

        summary, exit_code = batch_runner.run_batch_from_manifest(
            manifest_file=manifest_file,
            skill=skill,
            schema=schema,
            runs_dir=runs_dir,
            paper_trades_log=paper_trades_log,
            decision_log=decision_log,
            trigger="test_batch",
        )

        decision_rows = load_jsonl(decision_log)
        paper_trade_rows = load_jsonl(paper_trades_log)

        assert exit_code == 0, f"Expected batch exit_code 0, got {exit_code}"
        assert summary["total_runs"] == len(fixtures["runs"]), "Unexpected total_runs"
        assert summary["ok_runs"] == len(fixtures["runs"]), "Unexpected ok_runs"
        assert summary["error_runs"] == 0, "Unexpected error_runs"
        assert len(summary["runs"]) == len(fixtures["runs"]), "Unexpected run summary count"
        assert len(decision_rows) == len(fixtures["runs"]), "Unexpected decision log row count"
        assert len(paper_trade_rows) == 1, "Expected exactly one paper trade row"

        for item in summary["runs"]:
            expected = expected_by_label[item["run_label"]]
            assert item["decision"] == expected["expected_decision"], (
                f"{item['run_label']}: expected decision {expected['expected_decision']}, got {item['decision']}"
            )
            assert item["paper_trade_created"] == expected["expected_paper_trade_created"], (
                f"{item['run_label']}: unexpected paper_trade_created"
            )
            assert Path(item["decision_path"]).exists(), f"{item['run_label']}: decision file missing"

    print(f"PASS {len(fixtures['runs'])}/{len(fixtures['runs'])} structured automation batch scenarios")
    for fixture in fixtures["runs"]:
        print(
            f"- {fixture['run_label']}: decision={fixture['expected_decision']} "
            f"paper_trade_created={fixture['expected_paper_trade_created']}"
        )


if __name__ == "__main__":
    main()
