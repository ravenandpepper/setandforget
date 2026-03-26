import json
import tempfile
from pathlib import Path

import openclaw_tournament


BASE_DIR = Path(__file__).resolve().parent
FEATURE_SNAPSHOT_FILE = BASE_DIR / "feature_snapshot.example.json"
FEATURE_SCHEMA_FILE = BASE_DIR / "feature_snapshot_schema.json"
MODELS_FILE = BASE_DIR / "openclaw_tournament_models.example.json"
OUTPUT_SCHEMA_FILE = BASE_DIR / "openclaw_tournament_output_schema.json"
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
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_fake_runner(outputs_by_model_id: dict):
    def runner(model: dict, evaluation_payload: dict, primary_payload: dict, decision_schema: dict):
        del evaluation_payload, primary_payload, decision_schema
        return outputs_by_model_id[model["model_id"]]

    return runner


def run_completed_case():
    feature_payload = load_json(FEATURE_SNAPSHOT_FILE)
    feature_schema = load_json(FEATURE_SCHEMA_FILE)
    models_manifest = load_json(MODELS_FILE)
    output_schema = load_json(OUTPUT_SCHEMA_FILE)
    skill = load_json(SKILL_FILE)
    decision_schema = load_json(DECISION_SCHEMA_FILE)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        tournament_log = tmp_path / "openclaw_tournament_log.jsonl"
        fake_runner = build_fake_runner(
            {
                "openrouter/anthropic/claude-opus-4.6": {
                    "decision": "BUY",
                    "confidence_score": 66,
                    "reason_codes": ["HIGHER_TF_ALIGNED", "TREND_CONTINUATION"],
                    "summary": "Claude Opus sees continuation alignment across the objective snapshot.",
                },
                "openrouter/anthropic/claude-sonnet-4.6": {
                    "decision": "BUY",
                    "confidence_score": 61,
                    "reason_codes": ["HIGHER_TF_ALIGNED", "DAILY_TREND_CONFIRMED"],
                    "summary": "Claude Sonnet confirms the bullish continuation setup.",
                },
                "openrouter/minimax/minimax-m1": {
                    "decision": "BUY",
                    "confidence_score": 59,
                    "reason_codes": ["HIGHER_TF_ALIGNED", "RR_VALID"],
                    "summary": "Minimax accepts the setup with sufficient reward-to-risk.",
                },
                "openrouter/moonshotai/kimi-k2": {
                    "decision": "WAIT",
                    "confidence_score": 41,
                    "reason_codes": ["PULLBACK_NOT_CONFIRMED"],
                    "summary": "Kimi waits for a cleaner continuation trigger.",
                },
            }
        )
        result, exit_code = openclaw_tournament.run_tournament(
            feature_snapshot=feature_payload,
            feature_schema=feature_schema,
            models_manifest=models_manifest,
            output_schema=output_schema,
            skill=skill,
            decision_schema=decision_schema,
            runs_dir=tmp_path / "openclaw_tournament_runs",
            tournament_log=tournament_log,
            run_label="test",
            model_decision_runner=fake_runner,
        )

        assert exit_code == 0, "expected completed tournament run"
        assert result["status"] == "completed", "tournament should complete"
        assert result["primary_payload"]["decision"] == "BUY", "example baseline should stay BUY"
        assert len(result["entries"]) == 4, "expected one entry per configured model"
        assert Path(result["run"]["feature_snapshot_path"]).exists(), "feature snapshot artifact missing"
        assert Path(result["run"]["primary_payload_path"]).exists(), "primary payload artifact missing"
        assert Path(result["run"]["tournament_entries_path"]).exists(), "entries artifact missing"

        log_rows = load_jsonl(tournament_log)
        assert len(log_rows) == 4, "tournament log should contain one row per model"
        assert all(row["objective_only"] is True for row in log_rows), "all rows must remain objective-only"
        assert all(row["hard_gate_respected"] is True for row in log_rows), "all rows must respect hard gates"

    return {
        "id": "completed_shadow_tournament_logs_all_models",
        "entries": 4,
        "primary_decision": "BUY",
    }


def run_hard_gate_case():
    feature_payload = load_json(FEATURE_SNAPSHOT_FILE)
    feature_payload["operational_flags"]["open_trades_count"] = 2
    feature_schema = load_json(FEATURE_SCHEMA_FILE)
    models_manifest = load_json(MODELS_FILE)
    output_schema = load_json(OUTPUT_SCHEMA_FILE)
    skill = load_json(SKILL_FILE)
    decision_schema = load_json(DECISION_SCHEMA_FILE)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        fake_runner = build_fake_runner(
            {
                "openrouter/anthropic/claude-opus-4.6": {
                    "decision": "SELL",
                    "confidence_score": 42,
                    "reason_codes": ["HIGHER_TF_ALIGNED"],
                    "summary": "Claude Opus deliberately probes a contrarian outcome.",
                },
                "openrouter/anthropic/claude-sonnet-4.6": {
                    "decision": "BUY",
                    "confidence_score": 55,
                    "reason_codes": ["HIGHER_TF_ALIGNED", "TREND_CONTINUATION"],
                    "summary": "Claude Sonnet stays aligned with the primary trend case.",
                },
                "openrouter/minimax/minimax-m1": {
                    "decision": "BUY",
                    "confidence_score": 51,
                    "reason_codes": ["HIGHER_TF_ALIGNED", "RR_VALID"],
                    "summary": "Minimax would still buy without the primary hard gate.",
                },
                "openrouter/moonshotai/kimi-k2": {
                    "decision": "WAIT",
                    "confidence_score": 37,
                    "reason_codes": ["OPEN_TRADES_LIMIT_REACHED"],
                    "summary": "Kimi also waits when the trade budget is exhausted.",
                },
            }
        )
        result, exit_code = openclaw_tournament.run_tournament(
            feature_snapshot=feature_payload,
            feature_schema=feature_schema,
            models_manifest=models_manifest,
            output_schema=output_schema,
            skill=skill,
            decision_schema=decision_schema,
            runs_dir=tmp_path / "openclaw_tournament_runs",
            tournament_log=tmp_path / "openclaw_tournament_log.jsonl",
            run_label="hard-gate",
            model_decision_runner=fake_runner,
        )

        assert exit_code == 0, "hard gate case should still complete"
        assert result["primary_payload"]["decision"] == "WAIT", "primary baseline should block on open trade limit"

        minimax_entry = next(
            entry for entry in result["entries"] if entry["model_id"] == "openrouter/minimax/minimax-m1"
        )
        opus_entry = next(
            entry for entry in result["entries"] if entry["model_id"] == "openrouter/anthropic/claude-opus-4.6"
        )
        assert minimax_entry["decision"] == "WAIT", "Minimax must stay blocked by primary WAIT"
        assert minimax_entry["policy_enforced"] is True, "Minimax should be clamped by the hard gate policy"
        assert opus_entry["decision"] == "WAIT", "Opus must stay blocked by primary WAIT"
        assert opus_entry["policy_enforced"] is True, "Opus should also be clamped by the hard gate policy"

    return {
        "id": "primary_hard_gates_remain_non_overridable",
        "primary_decision": "WAIT",
        "policy_enforced_model": "openrouter/minimax/minimax-m1",
    }


def main():
    completed = run_completed_case()
    gated = run_hard_gate_case()
    print("PASS 2/2 openclaw tournament scenarios")
    print(
        f"- {completed['id']}: entries={completed['entries']} "
        f"primary_decision={completed['primary_decision']}"
    )
    print(
        f"- {gated['id']}: primary_decision={gated['primary_decision']} "
        f"policy_enforced_model={gated['policy_enforced_model']}"
    )


if __name__ == "__main__":
    main()
