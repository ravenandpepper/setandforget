import json
from datetime import UTC, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_STATUS_FILE = BASE_DIR / "openclaw_runtime_status.json"


def timestamp_now():
    return datetime.now(UTC).isoformat()


def load_status(path: Path):
    if not path.exists():
        return {
            "status_version": "1.0",
            "updated_at": None,
            "market_watch": None,
            "tournament": None,
        }

    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_status(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def update_status(path: Path, *, market_watch: dict | None = None, tournament: dict | None = None):
    payload = load_status(path)
    payload["status_version"] = "1.0"
    payload["updated_at"] = timestamp_now()
    if market_watch is not None:
        payload["market_watch"] = market_watch
    if tournament is not None:
        payload["tournament"] = tournament
    write_status(path, payload)
    return payload


def find_latest_run(rows: list[dict], *, predicate=None):
    latest = None
    for row in rows:
        if predicate is not None and not predicate(row):
            continue
        if latest is None:
            latest = row
            continue
        if (row.get("trigger_time", ""), row.get("pair", "")) >= (latest.get("trigger_time", ""), latest.get("pair", "")):
            latest = row
    return latest


def build_market_watch_status(summary: dict):
    bucket_runs = []
    for bucket in (summary.get("schedule") or {}).get("buckets", []):
        bucket_runs.extend(bucket.get("runs") or [])

    latest_success = find_latest_run(bucket_runs, predicate=lambda row: row.get("exit_code") == 0)
    latest_error = find_latest_run(bucket_runs, predicate=lambda row: row.get("exit_code") not in {None, 0})
    latest_run = find_latest_run(bucket_runs)

    return {
        "run_state": "completed" if summary.get("exit_code") == 0 else "completed_with_errors",
        "currently_running": False,
        "status": summary.get("status"),
        "updated_at": timestamp_now(),
        "trigger_time": ((summary.get("schedule") or {}).get("base_trigger_time") or (summary.get("guard") or {}).get("trigger_time")),
        "execution_timeframe": summary.get("execution_timeframe"),
        "execution_mode": summary.get("execution_mode"),
        "total_runs": summary.get("total_runs", 0),
        "ok_runs": summary.get("ok_runs", 0),
        "error_runs": summary.get("error_runs", 0),
        "skipped_runs": summary.get("skipped_runs", 0),
        "exit_code": summary.get("exit_code"),
        "guard": summary.get("guard"),
        "latest_run": latest_run,
        "latest_success": latest_success,
        "latest_error": latest_error,
    }


def build_market_watch_skipped_status(summary: dict):
    return {
        "run_state": "skipped",
        "currently_running": False,
        "status": summary.get("status"),
        "updated_at": timestamp_now(),
        "trigger_time": ((summary.get("schedule") or {}).get("base_trigger_time") or (summary.get("guard") or {}).get("trigger_time")),
        "execution_timeframe": summary.get("execution_timeframe"),
        "execution_mode": summary.get("execution_mode"),
        "total_runs": summary.get("total_runs", 0),
        "ok_runs": summary.get("ok_runs", 0),
        "error_runs": summary.get("error_runs", 0),
        "skipped_runs": summary.get("skipped_runs", 0),
        "exit_code": summary.get("exit_code"),
        "guard": summary.get("guard"),
        "latest_run": None,
        "latest_success": None,
        "latest_error": None,
    }


def build_tournament_started_status(run_id: str, feature_snapshot: dict, model_count: int):
    meta = feature_snapshot.get("meta") or {}
    return {
        "run_state": "running",
        "currently_running": True,
        "updated_at": timestamp_now(),
        "started_at": timestamp_now(),
        "completed_at": None,
        "last_result_status": None,
        "last_run_id": run_id,
        "pair": meta.get("pair"),
        "execution_timeframe": meta.get("execution_timeframe"),
        "execution_mode": meta.get("execution_mode"),
        "model_count": model_count,
        "latest_recorded_at": None,
        "latest_error": None,
    }


def build_tournament_finished_status(result: dict, exit_code: int):
    run = result.get("run") or {}
    entries = result.get("entries") or []
    latest_recorded_at = None
    if entries:
        latest_recorded_at = max((entry.get("recorded_at") or "" for entry in entries), default=None)

    latest_error = None
    for entry in entries:
        if "OUTPUT_SCHEMA_INVALID" in (entry.get("reason_codes") or []):
            latest_error = {
                "model_id": entry.get("model_id"),
                "summary": entry.get("summary"),
                "recorded_at": entry.get("recorded_at"),
            }

    return {
        "run_state": "completed" if exit_code == 0 else "failed",
        "currently_running": False,
        "updated_at": timestamp_now(),
        "started_at": None,
        "completed_at": timestamp_now(),
        "last_result_status": result.get("status"),
        "last_run_id": run.get("run_id"),
        "pair": (result.get("primary_payload") or {}).get("pair"),
        "execution_timeframe": (result.get("primary_payload") or {}).get("execution_timeframe"),
        "execution_mode": (result.get("primary_payload") or {}).get("execution_mode"),
        "model_count": run.get("model_count", len(entries)),
        "latest_recorded_at": latest_recorded_at,
        "latest_error": latest_error,
    }


def build_tournament_log_status(tournament_rows: list[dict]):
    latest_entry = None
    for row in tournament_rows:
        if latest_entry is None or row.get("recorded_at", "") >= latest_entry.get("recorded_at", ""):
            latest_entry = row

    if latest_entry is None:
        return {
            "run_state": "idle",
            "currently_running": False,
            "updated_at": timestamp_now(),
            "started_at": None,
            "completed_at": None,
            "last_result_status": None,
            "last_run_id": None,
            "pair": None,
            "execution_timeframe": None,
            "execution_mode": None,
            "model_count": 0,
            "latest_recorded_at": None,
            "latest_error": None,
        }

    latest_run_id = latest_entry.get("run_id")
    latest_run_entries = [row for row in tournament_rows if row.get("run_id") == latest_run_id]
    latest_error = None
    for row in latest_run_entries:
        if "OUTPUT_SCHEMA_INVALID" in (row.get("reason_codes") or []):
            latest_error = {
                "model_id": row.get("model_id"),
                "summary": row.get("summary"),
                "recorded_at": row.get("recorded_at"),
            }

    return {
        "run_state": "completed",
        "currently_running": False,
        "updated_at": timestamp_now(),
        "started_at": None,
        "completed_at": latest_entry.get("recorded_at"),
        "last_result_status": "completed",
        "last_run_id": latest_run_id,
        "pair": latest_entry.get("pair"),
        "execution_timeframe": latest_entry.get("execution_timeframe"),
        "execution_mode": latest_entry.get("execution_mode"),
        "model_count": len(latest_run_entries),
        "latest_recorded_at": latest_entry.get("recorded_at"),
        "latest_error": latest_error,
    }
