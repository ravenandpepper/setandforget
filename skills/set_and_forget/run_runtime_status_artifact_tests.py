import json
import tempfile
from pathlib import Path

import runtime_status_artifact as artifact


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def assert_market_watch_status_tracks_latest_error():
    summary = {
        "status": "completed",
        "execution_timeframe": "4H",
        "execution_mode": "paper",
        "exit_code": 1,
        "total_runs": 3,
        "ok_runs": 2,
        "error_runs": 1,
        "skipped_runs": 0,
        "guard": {
            "trigger_time": "2026-03-27T08:00:00Z",
        },
        "schedule": {
            "base_trigger_time": "2026-03-27T08:00:00Z",
            "buckets": [
                {
                    "runs": [
                        {
                            "pair": "GBPJPY",
                            "trigger_time": "2026-03-27T08:00:00Z",
                            "exit_code": 0,
                            "status": "processed",
                            "decision": "WAIT",
                            "validation_errors": [],
                        },
                        {
                            "pair": "EURGBP",
                            "trigger_time": "2026-03-27T08:01:00Z",
                            "exit_code": 1,
                            "status": "market_data_fetch_error",
                            "validation_errors": ["credits exhausted"],
                        },
                    ]
                }
            ],
        },
    }

    status = artifact.build_market_watch_status(summary)
    assert status["run_state"] == "completed_with_errors", "run state mismatch"
    assert status["latest_error"]["pair"] == "EURGBP", "latest error pair mismatch"
    assert status["latest_error"]["validation_errors"] == ["credits exhausted"], "latest error mismatch"


def assert_tournament_log_status_picks_latest_run():
    rows = [
        {
            "run_id": "run-1",
            "model_id": "model-a",
            "pair": "EURUSD",
            "execution_timeframe": "4H",
            "execution_mode": "paper",
            "recorded_at": "2026-03-26T16:50:00+00:00",
            "reason_codes": ["RR_VALID"],
            "summary": "ok",
        },
        {
            "run_id": "run-2",
            "model_id": "model-b",
            "pair": "EURUSD",
            "execution_timeframe": "4H",
            "execution_mode": "paper",
            "recorded_at": "2026-03-26T16:59:00+00:00",
            "reason_codes": ["OUTPUT_SCHEMA_INVALID"],
            "summary": "invalid output",
        },
    ]

    status = artifact.build_tournament_log_status(rows)
    assert status["last_run_id"] == "run-2", "latest run id mismatch"
    assert status["latest_error"]["model_id"] == "model-b", "latest tournament error mismatch"


def assert_update_status_merges_sections():
    with tempfile.TemporaryDirectory() as tmpdir:
        status_file = Path(tmpdir) / "openclaw_runtime_status.json"
        artifact.update_status(
            status_file,
            market_watch={"run_state": "completed"},
        )
        artifact.update_status(
            status_file,
            tournament={"run_state": "running", "last_run_id": "run-123"},
        )

        payload = load_json(status_file)

    assert payload["market_watch"]["run_state"] == "completed", "market watch section mismatch"
    assert payload["tournament"]["last_run_id"] == "run-123", "tournament section mismatch"


def main():
    assert_market_watch_status_tracks_latest_error()
    assert_tournament_log_status_picks_latest_run()
    assert_update_status_merges_sections()
    print("PASS 3/3 runtime status artifact scenarios")
    print("- market watch latest error summary ok")
    print("- tournament log latest run summary ok")
    print("- status file merge behavior ok")


if __name__ == "__main__":
    main()
