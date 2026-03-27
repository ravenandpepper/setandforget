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
MARKET_FIXTURES_FILE = BASE_DIR / "market_data_fetch_fixtures.json"


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
    def runner(
        model: dict,
        evaluation_payload: dict,
        primary_payload: dict,
        decision_schema: dict,
        *,
        model_reflection_snapshot: dict | None,
        run_id: str,
    ):
        del evaluation_payload, primary_payload, decision_schema, model_reflection_snapshot, run_id
        return outputs_by_model_id[model["model_id"]]

    return runner


def assert_prompt_and_session_contract():
    decision_schema = load_json(DECISION_SCHEMA_FILE)
    feature_payload = load_json(FEATURE_SNAPSHOT_FILE)
    evaluation_payload = {
        "feature_snapshot": feature_payload,
        "expected_output": decision_schema["expected_output"],
    }

    reflection_snapshot = {
        "model_id": "openrouter/anthropic/claude-opus-4.6",
        "peer_rank_by_pnl": 2,
        "self_review": "Tighten selectivity after the latest stop-out.",
    }
    prompt = json.loads(
        openclaw_tournament.build_openclaw_prompt(
            evaluation_payload,
            decision_schema,
            reflection_snapshot,
        )
    )
    assert "HIGHER_TF_ALIGNED" in prompt["allowed_reason_codes"], (
        "Prompt must expose the schema reason_code_catalog to the model"
    )
    assert "OUTPUT_SCHEMA_INVALID" in prompt["allowed_reason_codes"], (
        "Prompt must include the full reason_code_catalog"
    )
    assert prompt["model_reflection_snapshot"]["peer_rank_by_pnl"] == 2, (
        "Prompt should embed the latest per-model reflection snapshot when available"
    )
    assert any("model_reflection_snapshot" in rule for rule in prompt["rules"]), (
        "Prompt rules should explain that reflection is advisory only"
    )

    session_id = openclaw_tournament.build_openclaw_session_id(
        "20260326T155608632615Z_openclaw_tournament_eurusd_smoke",
        {"model_id": "openrouter/anthropic/claude-opus-4.6"},
    )
    retry_session_id = openclaw_tournament.build_openclaw_session_id(
        "20260326T155608632615Z_openclaw_tournament_eurusd_smoke",
        {"model_id": "openrouter/anthropic/claude-opus-4.6"},
        2,
    )
    assert session_id.startswith("setandforget_tournament_"), (
        "Tournament session ids should remain namespaced for OpenClaw"
    )
    assert "claude_opus_4_6" in session_id, (
        "Tournament session ids should include the model slug for traceability"
    )
    assert session_id != retry_session_id, (
        "Retry attempts should use distinct session ids to avoid reusing stale agent context"
    )
    extracted_text = openclaw_tournament.extract_first_text_payload(
        {
            "result": {
                "payloads": [
                    {"mediaUrl": "ignored"},
                    {"text": "  {\"decision\":\"WAIT\"}  "},
                ]
            }
        }
    )
    assert extracted_text.strip() == "{\"decision\":\"WAIT\"}", (
        "Payload extraction should scan for the first non-empty text payload"
    )
    assert openclaw_tournament.should_retry_openclaw_error(
        "OpenClaw agent response did not contain a text payload."
    ) is True, "Missing text payload should be retryable"

    with tempfile.TemporaryDirectory() as tmpdir:
        reflection_log = Path(tmpdir) / "openclaw_model_reflection_snapshots.jsonl"
        openclaw_tournament.append_jsonl(
            reflection_log,
            [
                {
                    "generated_at": "2026-03-26T16:00:00.000000+00:00",
                    "model_id": "openrouter/anthropic/claude-opus-4.6",
                    "peer_rank_by_pnl": 3,
                },
                {
                    "generated_at": "2026-03-26T16:30:00.000000+00:00",
                    "model_id": "openrouter/anthropic/claude-opus-4.6",
                    "peer_rank_by_pnl": 1,
                },
            ],
        )
        latest = openclaw_tournament.load_latest_model_reflections(reflection_log)
        assert latest["openrouter/anthropic/claude-opus-4.6"]["peer_rank_by_pnl"] == 1, (
            "Runner should use the latest reflection snapshot per model"
        )


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
        shadow_portfolio_log = tmp_path / "openclaw_shadow_portfolio_log.jsonl"
        settlement_log = tmp_path / "openclaw_shadow_portfolio_settlements.jsonl"
        reflection_log = tmp_path / "openclaw_model_reflection_snapshots.jsonl"
        openclaw_tournament.append_jsonl(
            reflection_log,
            [
                {
                    "generated_at": "2026-03-26T16:44:49.524408+00:00",
                    "model_id": "openrouter/anthropic/claude-opus-4.6",
                    "peer_rank_by_pnl": 1,
                    "self_review": "Preserve what is working.",
                },
                {
                    "generated_at": "2026-03-26T16:44:49.524465+00:00",
                    "model_id": "openrouter/moonshotai/kimi-k2",
                    "peer_rank_by_pnl": 4,
                    "self_review": "Contract reliability needs work.",
                },
            ],
        )
        fake_runner = build_fake_runner(
            {
                "openrouter/anthropic/claude-opus-4.6": {
                    "decision": "BUY",
                    "confidence_score": 66,
                    "reason_codes": ["HIGHER_TF_ALIGNED", "AOI_CONFLUENCE_STRONG"],
                    "summary": "Claude Opus sees continuation alignment across the objective snapshot.",
                },
                "openrouter/anthropic/claude-sonnet-4.6": {
                    "decision": "BUY",
                    "confidence_score": 61,
                    "reason_codes": ["HIGHER_TF_ALIGNED", "CONFIRMATION_PRESENT"],
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
                    "reason_codes": ["PULLBACK_NOT_PRESENT"],
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
            shadow_portfolio_log=shadow_portfolio_log,
            settlement_log=settlement_log,
            reflection_log=reflection_log,
            runtime_status_file=tmp_path / "openclaw_runtime_status.json",
            settlement_candles_file=MARKET_FIXTURES_FILE,
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
        assert Path(result["run"]["shadow_portfolio_tickets_path"]).exists(), "shadow portfolio artifact missing"
        assert result["post_run"] is not None, "post-run pipeline should execute when candles file is provided"
        assert Path(result["post_run"]["settlement"]["settlements_output_file"]).exists(), (
            "shadow settlement artifact missing"
        )
        assert Path(result["post_run"]["reflection"]["output_file"]).exists(), (
            "model reflection artifact missing"
        )

        log_rows = load_jsonl(tournament_log)
        shadow_rows = load_jsonl(shadow_portfolio_log)
        settlement_rows = load_jsonl(settlement_log)
        reflection_rows = load_jsonl(reflection_log)
        runtime_status = load_json(tmp_path / "openclaw_runtime_status.json")
        assert len(log_rows) == 4, "tournament log should contain one row per model"
        assert len(shadow_rows) == 4, "shadow portfolio log should contain one row per model"
        assert len(settlement_rows) == 4, "settlement log should contain one row per model"
        assert len(reflection_rows) >= 4, "reflection log should append one row per model snapshot"
        assert runtime_status["tournament"]["run_state"] == "completed", "runtime status should mark tournament complete"
        assert runtime_status["tournament"]["last_run_id"] == result["run"]["run_id"], "runtime run id mismatch"
        assert all(row["objective_only"] is True for row in log_rows), "all rows must remain objective-only"
        assert all(row["hard_gate_respected"] is True for row in log_rows), "all rows must respect hard gates"
        assert all("model_decision" in row for row in log_rows), "log rows should preserve raw model decisions"
        assert all("model_summary" in row for row in log_rows), "log rows should preserve raw model summaries"
        assert sum(1 for row in shadow_rows if row["shadow_trade_opened"]) == 3, (
            "three actionable model decisions should open shadow tickets"
        )
        assert any(row["outcome_status"] == "not_opened" for row in shadow_rows), (
            "non-actionable model decisions should stay not_opened"
        )
        assert result["post_run"]["settlement"]["closed_count"] == 3, (
            "three BUY shadow tickets should settle in the fixture outcome window"
        )
        assert result["post_run"]["reflection"]["snapshot_count"] == 4, (
            "reflection rebuild should emit one snapshot per model"
        )

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
                    "reason_codes": ["HIGHER_TF_ALIGNED", "RR_VALID"],
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
            shadow_portfolio_log=tmp_path / "openclaw_shadow_portfolio_log.jsonl",
            settlement_log=tmp_path / "openclaw_shadow_portfolio_settlements.jsonl",
            reflection_log=tmp_path / "openclaw_model_reflection_snapshots.jsonl",
            runtime_status_file=tmp_path / "openclaw_runtime_status.json",
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
        assert minimax_entry["model_decision"] == "BUY", "Minimax raw trade intent should remain visible"
        assert minimax_entry["policy_enforced"] is True, "Minimax should be clamped by the hard gate policy"
        assert opus_entry["decision"] == "WAIT", "Opus must stay blocked by primary WAIT"
        assert opus_entry["model_decision"] == "SELL", "Opus raw trade intent should remain visible"
        assert opus_entry["policy_enforced"] is True, "Opus should also be clamped by the hard gate policy"
        shadow_rows = load_jsonl(tmp_path / "openclaw_shadow_portfolio_log.jsonl")
        minimax_shadow = next(
            row for row in shadow_rows if row["model_id"] == "openrouter/minimax/minimax-m1"
        )
        assert minimax_shadow["decision"] == "WAIT", "Shadow ticket must record the clamped WAIT decision"
        assert minimax_shadow["shadow_trade_opened"] is False, "Clamped WAIT must not open a shadow trade"
        assert minimax_shadow["outcome_status"] == "not_opened", "Clamped WAIT must stay not_opened"

    return {
        "id": "primary_hard_gates_remain_non_overridable",
        "primary_decision": "WAIT",
        "policy_enforced_model": "openrouter/minimax/minimax-m1",
    }


def main():
    assert_prompt_and_session_contract()
    completed = run_completed_case()
    gated = run_hard_gate_case()
    print("PASS 3/3 openclaw tournament scenarios")
    print("- tournament_prompt_and_sessions_use_schema_contract: contract_ok=True")
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
