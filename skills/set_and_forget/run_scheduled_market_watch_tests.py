import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import run_scheduled_market_watch as market_watch


def write_json(path: Path, payload: dict):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def assert_load_runtime_config_normalizes_pairs():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "scheduled_market_watch.json"
        write_json(
            config_path,
            {
                "pairs": [" gbpjpy ", "EURJPY", "", "EURGBP"],
                "execution_timeframe": "4H",
                "execution_mode": "paper",
                "max_requests_per_minute": 8,
                "minute_spacing": 2,
                "fxalex_confluence_enabled": True,
            },
        )

        config = market_watch.load_runtime_config(config_path)

    assert config["pairs"] == ["GBPJPY", "EURJPY", "EURGBP"], "pair normalization mismatch"
    assert config["execution_timeframe"] == "4H", "execution timeframe mismatch"
    assert config["execution_mode"] == "paper", "execution mode mismatch"
    assert config["max_requests_per_minute"] == 8, "max request budget mismatch"
    assert config["minute_spacing"] == 2, "minute spacing mismatch"
    assert config["fxalex_confluence_enabled"] is True, "fxalex flag mismatch"
    assert config["news_context_enabled"] is False, "news context default mismatch"


def assert_load_runtime_config_requires_pairs():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "scheduled_market_watch.json"
        write_json(config_path, {"pairs": []})
        try:
            market_watch.load_runtime_config(config_path)
        except ValueError as error:
            assert "requires at least one pair" in str(error), f"unexpected error: {error}"
            return

    raise AssertionError("expected a ValueError for missing pairs")


def assert_run_scheduled_market_watch_forwards_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_path = tmp_path / "scheduled_market_watch.json"
        write_json(
            config_path,
            {
                "pairs": ["GBPJPY", "EURJPY", "EURGBP"],
                "execution_timeframe": "4H",
                "execution_mode": "paper",
                "max_requests_per_minute": 6,
                "minute_spacing": 1,
                "fxalex_confluence_enabled": False,
                "news_context_enabled": False,
            },
        )
        webhook_schema_file = tmp_path / "webhook.json"
        skill_file = tmp_path / "skill.json"
        decision_schema_file = tmp_path / "decision.json"
        write_json(webhook_schema_file, {"schema": "webhook"})
        write_json(skill_file, {"skill": "set_and_forget"})
        write_json(decision_schema_file, {"schema": "decision"})

        observed = {}

        def fake_run(**kwargs):
            observed.update(kwargs)
            return {
                "status": "skipped_by_guard",
                "guard": {"eligible": False, "skip_reason_code": "H4_NOT_CLOSED"},
                "provider": "twelvedata",
                "adapter": "twelvedata",
                "execution_timeframe": "4H",
                "execution_mode": "paper",
                "request_budget": {},
                "schedule": {"buckets": []},
                "total_runs": 0,
                "ok_runs": 0,
                "error_runs": 0,
                "skipped_runs": 3,
                "exit_code": 0,
            }, 0

        with patch.object(market_watch.batch_runner, "run_scheduled_trigger_batch", side_effect=fake_run), patch.object(
            market_watch.batch_runner,
            "emit_output",
            return_value=None,
        ):
            _, exit_code = market_watch.run_scheduled_market_watch(
                config_file=config_path,
                trigger_time="2026-03-27T08:00:00Z",
                output_format="json",
                runs_dir=tmp_path / "runs",
                paper_trades_log=tmp_path / "paper_trades_log.jsonl",
                decision_log=tmp_path / "decision_log.jsonl",
                webhook_schema_file=webhook_schema_file,
                skill_file=skill_file,
                decision_schema_file=decision_schema_file,
                enforce_run_guard=True,
            )

    assert exit_code == 0, "exit code mismatch"
    assert observed["pairs"] == ["GBPJPY", "EURJPY", "EURGBP"], "pairs forwarding mismatch"
    assert observed["trigger_time"] == "2026-03-27T08:00:00Z", "trigger time forwarding mismatch"
    assert observed["execution_timeframe"] == "4H", "execution timeframe forwarding mismatch"
    assert observed["execution_mode"] == "paper", "execution mode forwarding mismatch"
    assert observed["max_requests_per_minute"] == 6, "request budget forwarding mismatch"
    assert observed["minute_spacing"] == 1, "minute spacing forwarding mismatch"
    assert observed["enforce_run_guard"] is True, "guard forwarding mismatch"


def main():
    assert_load_runtime_config_normalizes_pairs()
    assert_load_runtime_config_requires_pairs()
    assert_run_scheduled_market_watch_forwards_config()
    print("PASS 3/3 scheduled market watch scenarios")
    print("- config normalization ok")
    print("- missing pairs rejected")
    print("- batch runner wiring ok")


if __name__ == "__main__":
    main()
