import json
from pathlib import Path

import openclaw_tournament
import runtime_status_artifact
import telegram_notify


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = BASE_DIR / "live_tournament_sidecar.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_path(value: str | None, default: Path | None):
    if default is None and not value:
        return None
    if not value:
        return default
    path = Path(value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def load_runtime_config(config_file: Path):
    payload = {}
    if config_file.exists():
        payload = load_json(config_file)

    return {
        "enabled": bool(payload.get("enabled", False)),
        "run_label": payload.get("run_label") or "live_sidecar",
        "feature_schema_file": resolve_path(payload.get("feature_schema_file"), openclaw_tournament.FEATURE_SNAPSHOT_SCHEMA_FILE),
        "models_file": resolve_path(payload.get("models_file"), openclaw_tournament.MODELS_FILE),
        "output_schema_file": resolve_path(payload.get("output_schema_file"), openclaw_tournament.OUTPUT_SCHEMA_FILE),
        "runs_dir": resolve_path(payload.get("runs_dir"), openclaw_tournament.TOURNAMENT_RUNS_DIR),
        "tournament_log": resolve_path(payload.get("tournament_log"), openclaw_tournament.TOURNAMENT_LOG_FILE),
        "shadow_portfolio_log": resolve_path(payload.get("shadow_portfolio_log"), openclaw_tournament.TOURNAMENT_SHADOW_PORTFOLIO_LOG_FILE),
        "settlement_log": resolve_path(payload.get("settlement_log"), openclaw_tournament.TOURNAMENT_SHADOW_SETTLEMENT_LOG_FILE),
        "reflection_log": resolve_path(payload.get("reflection_log"), openclaw_tournament.MODEL_REFLECTION_LOG_FILE),
        "runtime_status_file": resolve_path(payload.get("runtime_status_file"), runtime_status_artifact.DEFAULT_STATUS_FILE),
        "settlement_candles_file": resolve_path(payload.get("settlement_candles_file"), None) if payload.get("settlement_candles_file") else None,
    }


def refresh_tournament_runtime_status(runtime_config: dict):
    tournament_rows = openclaw_tournament.load_json_rows(runtime_config["tournament_log"])
    runtime_status_artifact.update_status(
        runtime_config["runtime_status_file"],
        tournament=runtime_status_artifact.build_tournament_log_status(tournament_rows),
    )


def run_live_tournament_sidecar(
    *,
    feature_snapshot: dict,
    skill: dict,
    decision_schema: dict,
    config_file: Path = DEFAULT_CONFIG_FILE,
):
    runtime_config = load_runtime_config(config_file)
    if not runtime_config["enabled"]:
        refresh_tournament_runtime_status(runtime_config)
        return {
            "status": "disabled",
            "enabled": False,
            "config_file": str(config_file),
        }, 0

    try:
        result, exit_code = openclaw_tournament.run_tournament(
            feature_snapshot=feature_snapshot,
            feature_schema=openclaw_tournament.load_json(runtime_config["feature_schema_file"]),
            models_manifest=openclaw_tournament.load_json(runtime_config["models_file"]),
            output_schema=openclaw_tournament.load_json(runtime_config["output_schema_file"]),
            skill=skill,
            decision_schema=decision_schema,
            runs_dir=runtime_config["runs_dir"],
            tournament_log=runtime_config["tournament_log"],
            shadow_portfolio_log=runtime_config["shadow_portfolio_log"],
            settlement_log=runtime_config["settlement_log"],
            reflection_log=runtime_config["reflection_log"],
            runtime_status_file=runtime_config["runtime_status_file"],
            settlement_candles_file=runtime_config["settlement_candles_file"],
            run_label=runtime_config["run_label"],
        )
    except Exception as exc:
        refresh_tournament_runtime_status(runtime_config)
        return {
            "status": "sidecar_error",
            "enabled": True,
            "config_file": str(config_file),
            "error": str(exc),
        }, 1

    telegram_notification = None
    if result.get("status") == "completed":
        telegram_notification = telegram_notify.maybe_send_tournament_report_notification(result)

    return {
        "status": "completed" if exit_code == 0 else "error",
        "enabled": True,
        "config_file": str(config_file),
        "result": result,
        "telegram_notification": telegram_notification,
    }, exit_code
