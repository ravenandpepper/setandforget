import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import live_tournament_sidecar as sidecar


def write_json(path: Path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def assert_disabled_sidecar_refreshes_runtime_status():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        tournament_log = tmp_path / "openclaw_tournament_log.jsonl"
        tournament_log.write_text(
            json.dumps(
                {
                    "run_id": "run-123",
                    "model_id": "model-a",
                    "pair": "EURUSD",
                    "execution_timeframe": "4H",
                    "execution_mode": "paper",
                    "recorded_at": "2026-03-26T16:59:09+00:00",
                    "reason_codes": ["RR_VALID"],
                    "summary": "ok",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        config_file = tmp_path / "live_tournament_sidecar.json"
        runtime_status_file = tmp_path / "openclaw_runtime_status.json"
        write_json(
            config_file,
            {
                "enabled": False,
                "tournament_log": str(tournament_log),
                "runtime_status_file": str(runtime_status_file),
            },
        )

        result, exit_code = sidecar.run_live_tournament_sidecar(
            feature_snapshot={"meta": {"pair": "EURUSD", "execution_timeframe": "4H", "execution_mode": "paper"}},
            skill={},
            decision_schema={},
            config_file=config_file,
        )
        status_payload = load_json(runtime_status_file)

    assert exit_code == 0, "disabled sidecar should not fail"
    assert result["status"] == "disabled", "disabled sidecar status mismatch"
    assert status_payload["tournament"]["last_run_id"] == "run-123", "runtime status should track latest tournament run"


def assert_enabled_sidecar_calls_tournament_runner():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_file = tmp_path / "live_tournament_sidecar.json"
        write_json(
            config_file,
            {
                "enabled": True,
                "feature_schema_file": str(tmp_path / "feature_schema.json"),
                "models_file": str(tmp_path / "models.json"),
                "output_schema_file": str(tmp_path / "output_schema.json"),
                "runs_dir": str(tmp_path / "runs"),
                "tournament_log": str(tmp_path / "openclaw_tournament_log.jsonl"),
                "shadow_portfolio_log": str(tmp_path / "openclaw_shadow_portfolio_log.jsonl"),
                "settlement_log": str(tmp_path / "openclaw_shadow_portfolio_settlements.jsonl"),
                "reflection_log": str(tmp_path / "openclaw_model_reflection_snapshots.jsonl"),
                "runtime_status_file": str(tmp_path / "openclaw_runtime_status.json"),
                "run_label": "test_sidecar",
            },
        )
        write_json(tmp_path / "feature_schema.json", {"schema": "feature"})
        write_json(tmp_path / "models.json", {"models": []})
        write_json(tmp_path / "output_schema.json", {"fields": []})

        fake_result = {
            "status": "completed",
            "run": {"run_id": "run-456"},
            "primary_payload": {
                "pair": "EURUSD",
                "execution_timeframe": "4H",
                "decision": "WAIT",
                "confidence_score": 48,
            },
            "entries": [
                {
                    "model_id": "openrouter/anthropic/claude-opus-4.6",
                    "model_decision": "BUY",
                    "model_confidence_score": 66,
                    "model_summary": "Opus zag trend alignment en confirmation.",
                    "decision": "WAIT",
                    "policy_enforced": True,
                    "summary": "Hard gate enforced.",
                }
            ],
        }
        with (
            patch.object(sidecar.openclaw_tournament, "run_tournament", return_value=(fake_result, 0)) as patched,
            patch.object(
                sidecar.telegram_notify,
                "maybe_send_tournament_report_notification",
                return_value={"sent": True, "status": "sent"},
            ) as notify_patched,
        ):
            result, exit_code = sidecar.run_live_tournament_sidecar(
                feature_snapshot={"meta": {"pair": "EURUSD", "execution_timeframe": "4H", "execution_mode": "paper"}},
                skill={"skill": "set_and_forget"},
                decision_schema={"schema": "decision"},
                config_file=config_file,
            )

    assert exit_code == 0, "enabled sidecar should forward successful exit code"
    assert result["status"] == "completed", "enabled sidecar status mismatch"
    assert patched.called, "tournament runner should be invoked when sidecar is enabled"
    assert notify_patched.called, "completed sidecar runs should send a tournament report notification"
    assert result["telegram_notification"]["sent"] is True, "notification result should be exposed in sidecar output"


def main():
    assert_disabled_sidecar_refreshes_runtime_status()
    assert_enabled_sidecar_calls_tournament_runner()
    print("PASS 2/2 live tournament sidecar scenarios")
    print("- disabled sidecar refreshes runtime status")
    print("- enabled sidecar calls tournament runner and reports via telegram")


if __name__ == "__main__":
    main()
