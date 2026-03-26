import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import run_market_watch_status as status_script


def write_json(path: Path, payload: dict):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def write_jsonl(path: Path, rows: list[dict]):
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row))
            handle.write("\n")


def assert_parse_systemctl_show_output():
    payload = status_script.parse_systemctl_show_output(
        "Id=setandforget-market-watch.timer\nActiveState=active\nSubState=waiting\n"
    )
    assert payload["Id"] == "setandforget-market-watch.timer", "unit id mismatch"
    assert payload["ActiveState"] == "active", "active state mismatch"
    assert payload["SubState"] == "waiting", "sub state mismatch"


def assert_run_command_handles_missing_binary():
    result = status_script.run_command(["definitely_missing_binary_for_test"])
    assert result["ok"] is False, "missing binary should fail"
    assert result["returncode"] == 127, "missing binary return code mismatch"
    assert "No such file or directory" in result["stderr"], "missing binary stderr mismatch"


def assert_extract_latest_guard_line():
    line = status_script.extract_latest_guard_line(
        [
            "2026-03-26 line one",
            "2026-03-26 Guard: eligible=False skip_reason_code=H4_NOT_CLOSED | Off cycle",
        ]
    )
    assert line.endswith("skip_reason_code=H4_NOT_CLOSED | Off cycle"), "guard extraction mismatch"


def assert_build_market_watch_status_summary():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config_file = tmp_path / "scheduled_market_watch.json"
        decision_log = tmp_path / "automation_decisions_log.jsonl"
        paper_trades_log = tmp_path / "paper_trades_log.jsonl"
        write_json(
            config_file,
            {
                "pairs": ["GBPJPY", "EURJPY", "EURGBP"],
                "execution_timeframe": "4H",
                "execution_mode": "paper",
            },
        )
        write_jsonl(
            decision_log,
            [
                {
                    "timestamp": "2026-03-27T08:00:05Z",
                    "pair": "EURGBP",
                    "decision": "BUY",
                    "paper_trade_created": True,
                }
            ],
        )
        write_jsonl(
            paper_trades_log,
            [
                {
                    "timestamp": "2026-03-27T08:00:06Z",
                    "pair": "EURGBP",
                    "decision": "BUY",
                    "confidence_score": 82,
                }
            ],
        )

        with patch.object(
            status_script,
            "read_unit_show",
            side_effect=[
                {
                    "available": True,
                    "ActiveState": "active",
                    "SubState": "waiting",
                    "NextElapseUSecRealtime": "Fri 2026-03-27 09:00:00 CET",
                    "LastTriggerUSec": "Thu 2026-03-26 20:00:00 CET",
                },
                {
                    "available": True,
                    "ActiveState": "inactive",
                    "SubState": "dead",
                    "Result": "success",
                },
            ],
        ), patch.object(
            status_script,
            "read_recent_service_journal",
            return_value={
                "available": True,
                "lines": [
                    "2026-03-26 19:37:04 python3[1]: Runs: total=0 ok=0 error=0 | exit_code=0",
                    "2026-03-26 19:37:04 python3[1]: Guard: eligible=False skip_reason_code=H4_NOT_CLOSED | Off cycle",
                ],
                "error": None,
            },
        ):
            status = status_script.build_market_watch_status(
                config_file=config_file,
                decision_log=decision_log,
                paper_trades_log=paper_trades_log,
                timer_unit="setandforget-market-watch.timer",
                service_unit="setandforget-market-watch.service",
                journal_lines=20,
            )

    assert status["config"]["pairs"] == ["GBPJPY", "EURJPY", "EURGBP"], "config pairs mismatch"
    assert status["timer"]["ActiveState"] == "active", "timer state mismatch"
    assert status["service"]["Result"] == "success", "service result mismatch"
    assert status["journal"]["latest_guard_line"].endswith("skip_reason_code=H4_NOT_CLOSED | Off cycle"), (
        "latest guard mismatch"
    )
    assert status["last_decision"]["row"]["pair"] == "EURGBP", "last decision mismatch"
    assert status["last_trade"]["row"]["confidence_score"] == 82, "last trade mismatch"


def main():
    assert_parse_systemctl_show_output()
    assert_run_command_handles_missing_binary()
    assert_extract_latest_guard_line()
    assert_build_market_watch_status_summary()
    print("PASS 4/4 market watch status scenarios")
    print("- systemctl parsing ok")
    print("- missing binary fallback ok")
    print("- journal guard extraction ok")
    print("- market watch summary wiring ok")


if __name__ == "__main__":
    main()
