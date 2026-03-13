import json
from pathlib import Path

import run_set_and_forget as engine
import run_structured_automation as automation


BASE_DIR = Path(__file__).resolve().parent
WEBHOOK_SCHEMA_FILE = BASE_DIR / "tradingview_webhook_schema.json"

SNAPSHOT_FIELDS = [
    "pair",
    "execution_timeframe",
    "execution_mode",
    "fxalex_confluence_enabled",
    "news_context_enabled",
    "weekly_trend",
    "daily_trend",
    "h4_pullback_direction",
    "h4_pullback_structure",
    "h4_reversal_state",
    "h4_break_of_structure",
    "first_entry_structure",
    "aoi_zone_status",
    "aoi_confluence_count",
    "aoi_has_sr",
    "aoi_has_order_block",
    "aoi_has_structural_level",
    "confirmation_present",
    "confirmation_type",
    "stop_loss_basis",
    "risk_reward_ratio",
    "planned_risk_percent",
    "open_trades_count",
    "high_impact_news_imminent",
    "session_window",
    "set_and_forget_possible",
    "entry_price",
    "stop_loss_price",
    "take_profit_price",
    "notes",
]


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_pair(value):
    if not value:
        return None

    token = str(value).strip().upper()
    if ":" in token:
        token = token.split(":")[-1]
    if "." in token:
        token = token.split(".")[0]
    return token or None


def normalize_timeframe(value):
    if not value:
        return None

    token = str(value).strip().upper()
    mapping = {
        "240": "4H",
        "4H": "4H",
        "4HR": "4H",
        "4HOUR": "4H",
    }
    return mapping.get(token, token)


def canonicalize_alert_payload(alert_payload: dict):
    canonical = dict(alert_payload)
    canonical["source"] = str(alert_payload.get("source", "")).strip().lower()
    canonical["message_version"] = alert_payload.get("message_version", "tv_webhook_v1")
    canonical["pair"] = normalize_pair(
        alert_payload.get("pair")
        or alert_payload.get("symbol")
        or alert_payload.get("ticker")
    )
    canonical["execution_timeframe"] = normalize_timeframe(
        alert_payload.get("execution_timeframe")
        or alert_payload.get("timeframe")
        or alert_payload.get("interval")
    )
    canonical["execution_mode"] = alert_payload.get("execution_mode", "paper")
    canonical["fxalex_confluence_enabled"] = alert_payload.get("fxalex_confluence_enabled", False)
    canonical["news_context_enabled"] = alert_payload.get("news_context_enabled", False)
    return canonical


def validate_tradingview_alert(alert_payload: dict, schema: dict):
    canonical = canonicalize_alert_payload(alert_payload)
    return canonical, engine.validate_snapshot(canonical, schema)


def build_snapshot_from_alert(alert_payload: dict):
    canonical = canonicalize_alert_payload(alert_payload)
    snapshot = {}
    for field in SNAPSHOT_FIELDS:
        if field in canonical:
            snapshot[field] = canonical[field]

    if "notes" not in snapshot:
        snapshot["notes"] = build_snapshot_note(canonical)
    return snapshot


def build_snapshot_note(canonical_alert: dict):
    parts = ["TradingView webhook ingest"]
    if canonical_alert.get("alert_name"):
        parts.append(canonical_alert["alert_name"])
    if canonical_alert.get("trigger_time"):
        parts.append(canonical_alert["trigger_time"])
    return " | ".join(parts)


def build_alert_context(canonical_alert: dict):
    return {
        "source": canonical_alert.get("source"),
        "message_version": canonical_alert.get("message_version"),
        "alert_name": canonical_alert.get("alert_name"),
        "ticker": canonical_alert.get("ticker"),
        "exchange": canonical_alert.get("exchange"),
        "trigger_time": canonical_alert.get("trigger_time"),
        "normalized_pair": canonical_alert.get("pair"),
        "normalized_execution_timeframe": canonical_alert.get("execution_timeframe"),
    }


def run_tradingview_ingest(
    alert_payload: dict,
    webhook_schema: dict,
    skill: dict,
    decision_schema: dict,
    runs_dir: Path,
    paper_trades_log: Path,
    decision_log: Path,
):
    canonical_alert, webhook_errors = validate_tradingview_alert(alert_payload, webhook_schema)
    if webhook_errors:
        return {
            "status": "invalid_alert",
            "alert_context": build_alert_context(canonical_alert),
            "validation": {
                "ok": False,
                "errors": webhook_errors,
            },
            "snapshot": None,
            "automation": None,
        }, 1

    snapshot = build_snapshot_from_alert(canonical_alert)
    snapshot_errors = engine.validate_snapshot(snapshot, decision_schema)
    if snapshot_errors:
        return {
            "status": "invalid_snapshot",
            "alert_context": build_alert_context(canonical_alert),
            "validation": {
                "ok": False,
                "errors": snapshot_errors,
            },
            "snapshot": snapshot,
            "automation": None,
        }, 1

    automation_result, exit_code = automation.run_structured_automation(
        snapshot=snapshot,
        skill=skill,
        schema=decision_schema,
        runs_dir=runs_dir,
        paper_trades_log=paper_trades_log,
        decision_log=decision_log,
        trigger="tradingview_webhook",
        run_label=canonical_alert.get("alert_name") or canonical_alert.get("pair"),
    )

    return {
        "status": "processed",
        "alert_context": build_alert_context(canonical_alert),
        "validation": {
            "ok": True,
            "errors": [],
        },
        "snapshot": snapshot,
        "automation": automation_result,
    }, exit_code
