import json
from pathlib import Path

import market_data_fetch
import market_data_ingest
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
COMMON_FIELDS = {
    "source",
    "message_version",
    "pair",
    "execution_timeframe",
    "execution_mode",
    "fxalex_confluence_enabled",
    "news_context_enabled",
    "ticker",
    "exchange",
    "trigger_time",
    "alert_name",
    "payload_kind",
}


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
    canonical["payload_kind"] = str(alert_payload.get("payload_kind", "")).strip().lower() or None
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


def is_candle_bundle_alert(canonical_alert: dict):
    payload_kind = canonical_alert.get("payload_kind")
    if payload_kind == "candle_bundle":
        return True
    return (
        isinstance(canonical_alert.get("candles"), dict)
        and "risk_features" in canonical_alert
        and "operational_flags" in canonical_alert
    )


def is_trigger_only_alert(canonical_alert: dict):
    return canonical_alert.get("payload_kind") == "trigger_only"


def validate_common_tradingview_fields(canonical: dict, schema: dict):
    filtered_payload = {field["name"]: canonical.get(field["name"]) for field in schema["fields"] if field["name"] in COMMON_FIELDS and field["name"] in canonical}
    filtered_schema = {
        **schema,
        "fields": [field for field in schema["fields"] if field["name"] in COMMON_FIELDS],
    }
    return engine.validate_snapshot(filtered_payload, filtered_schema)


def validate_tradingview_alert(alert_payload: dict, schema: dict):
    canonical = canonicalize_alert_payload(alert_payload)
    validation_schema = schema
    if is_trigger_only_alert(canonical):
        validation_schema = market_data_fetch.load_json(
            BASE_DIR / "tradingview_trigger_only_schema.json"
        )

    common_errors = validate_common_tradingview_fields(canonical, validation_schema)
    if common_errors:
        return canonical, common_errors

    if is_trigger_only_alert(canonical):
        return canonical, []

    if is_candle_bundle_alert(canonical):
        ingest_schema = market_data_ingest.load_json(market_data_ingest.INGEST_SCHEMA_FILE)
        ingest_payload = build_ingest_payload_from_alert(canonical)
        return canonical, market_data_ingest.validate_ingest_payload(ingest_payload, ingest_schema)

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


def build_ingest_payload_from_alert(canonical_alert: dict):
    return {
        "pair": canonical_alert.get("pair"),
        "execution_timeframe": canonical_alert.get("execution_timeframe"),
        "execution_mode": canonical_alert.get("execution_mode", "paper"),
        "source_kind": "market_data_pipeline",
        "generated_at": canonical_alert.get("trigger_time"),
        "fxalex_confluence_enabled": canonical_alert.get("fxalex_confluence_enabled", False),
        "news_context_enabled": canonical_alert.get("news_context_enabled", False),
        "candles": canonical_alert["candles"],
        "risk_features": canonical_alert["risk_features"],
        "operational_flags": canonical_alert["operational_flags"],
        "aoi_features": canonical_alert.get("aoi_features"),
        "confirmation_features": canonical_alert.get("confirmation_features"),
    }


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

    if is_trigger_only_alert(canonical_alert):
        fetch_result, fetch_exit_code = market_data_fetch.run_trigger_fetch_prep(canonical_alert)
        if fetch_exit_code != 0:
            return {
                "status": fetch_result["status"],
                "alert_context": build_alert_context(canonical_alert),
                "validation": {
                    "ok": False,
                    "errors": fetch_result.get("errors", []),
                },
                "snapshot": None,
                "market_input": None,
                "market_data_fetch": fetch_result,
                "automation": None,
            }, 1

        ingest_schema = market_data_ingest.load_json(market_data_ingest.INGEST_SCHEMA_FILE)
        feature_schema = market_data_ingest.load_json(BASE_DIR / "feature_snapshot_schema.json")
        input_schema = market_data_ingest.load_json(BASE_DIR / "market_structure_input_schema.json")
        ingest_result, exit_code = market_data_ingest.run_market_data_ingest(
            ingest_payload=fetch_result["ingest_payload"],
            ingest_schema=ingest_schema,
            input_schema=input_schema,
            feature_schema=feature_schema,
            skill=skill,
            decision_schema=decision_schema,
            runs_dir=runs_dir,
            paper_trades_log=paper_trades_log,
            decision_log=decision_log,
            trigger="tradingview_trigger_only",
        )
        return {
            "status": "processed" if exit_code == 0 else ingest_result["status"],
            "alert_context": build_alert_context(canonical_alert),
            "validation": {
                "ok": exit_code == 0,
                "errors": ingest_result.get("errors", []),
            },
            "snapshot": None,
            "market_input": ingest_result.get("market_input"),
            "market_data_fetch": fetch_result,
            "automation": ingest_result.get("decision_run", {}).get("automation") if ingest_result.get("decision_run") else None,
        }, exit_code

    if is_candle_bundle_alert(canonical_alert):
        ingest_schema = market_data_ingest.load_json(market_data_ingest.INGEST_SCHEMA_FILE)
        feature_schema = market_data_ingest.load_json(BASE_DIR / "feature_snapshot_schema.json")
        input_schema = market_data_ingest.load_json(BASE_DIR / "market_structure_input_schema.json")
        ingest_payload = build_ingest_payload_from_alert(canonical_alert)
        ingest_result, exit_code = market_data_ingest.run_market_data_ingest(
            ingest_payload=ingest_payload,
            ingest_schema=ingest_schema,
            input_schema=input_schema,
            feature_schema=feature_schema,
            skill=skill,
            decision_schema=decision_schema,
            runs_dir=runs_dir,
            paper_trades_log=paper_trades_log,
            decision_log=decision_log,
            trigger="tradingview_webhook",
        )
        return {
            "status": "processed" if exit_code == 0 else ingest_result["status"],
            "alert_context": build_alert_context(canonical_alert),
            "validation": {
                "ok": exit_code == 0,
                "errors": ingest_result.get("errors", []),
            },
            "snapshot": None,
            "market_input": ingest_result.get("market_input"),
            "market_data_fetch": None,
            "automation": ingest_result.get("decision_run", {}).get("automation") if ingest_result.get("decision_run") else None,
        }, exit_code

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
            "market_input": None,
            "market_data_fetch": None,
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
        "market_input": None,
        "market_data_fetch": None,
        "automation": automation_result,
    }, exit_code
