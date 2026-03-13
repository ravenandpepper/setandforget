import json
from pathlib import Path

import market_structure
import run_market_structure_to_decision as market_runner


BASE_DIR = Path(__file__).resolve().parent
INGEST_SCHEMA_FILE = BASE_DIR / "market_data_ingest_schema.json"
ALLOWED_SOURCE_KINDS = {"market_data_pipeline", "manual_fixture", "automation"}


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


def normalize_timeframe(value, schema: dict):
    if not value:
        return None

    token = str(value).strip().upper()
    aliases = schema.get("supported_timeframe_aliases", {})
    return aliases.get(token, token)


def normalize_source_kind(value):
    token = str(value).strip() if value is not None else ""
    if token in ALLOWED_SOURCE_KINDS:
        return token
    return "market_data_pipeline"


def validate_ingest_payload(payload: dict, schema: dict):
    errors = []
    for field in schema.get("required_fields", []):
        if field not in payload:
            errors.append(f"Missing required field: {field}")

    candles = payload.get("candles")
    if candles is not None and not isinstance(candles, dict):
        errors.append("Field candles must be an object.")
    elif isinstance(candles, dict):
        for timeframe in schema.get("timeframes", []):
            if timeframe not in candles:
                errors.append(f"Missing required candle timeframe: candles.{timeframe}")
            elif not isinstance(candles[timeframe], list):
                errors.append(f"Field candles.{timeframe} must be an array.")

    return errors


def build_market_input_from_payload(payload: dict, schema: dict):
    objective_context = {
        "risk_features": payload["risk_features"],
        "operational_flags": payload["operational_flags"],
    }
    if payload.get("aoi_features") is not None:
        objective_context["aoi_features"] = payload["aoi_features"]
    if payload.get("confirmation_features") is not None:
        objective_context["confirmation_features"] = payload["confirmation_features"]

    return {
        "meta": {
            "pair": normalize_pair(payload.get("pair") or payload.get("symbol") or payload.get("ticker")),
            "execution_timeframe": normalize_timeframe(
                payload.get("execution_timeframe") or payload.get("timeframe") or payload.get("interval"),
                schema,
            ),
            "execution_mode": payload.get("execution_mode", "paper"),
            "source_kind": normalize_source_kind(payload.get("source_kind")),
            "generated_at": payload.get("generated_at"),
            "fxalex_confluence_enabled": payload.get("fxalex_confluence_enabled", False),
            "news_context_enabled": payload.get("news_context_enabled", False),
        },
        "candles": {
            "weekly": {"candles": payload["candles"]["weekly"]},
            "daily": {"candles": payload["candles"]["daily"]},
            "h4": {"candles": payload["candles"]["h4"]},
        },
        "objective_context": objective_context,
    }


def run_market_data_ingest(
    ingest_payload: dict,
    ingest_schema: dict,
    input_schema: dict,
    feature_schema: dict,
    skill: dict,
    decision_schema: dict,
    runs_dir: Path,
    paper_trades_log: Path,
    decision_log: Path,
    trigger: str = "market_data_ingest",
):
    ingest_errors = validate_ingest_payload(ingest_payload, ingest_schema)
    if ingest_errors:
        return {
            "status": "invalid_ingest_payload",
            "stage": "ingest_payload_validation",
            "errors": ingest_errors,
            "market_input": None,
            "decision_run": None,
        }, 1

    market_input = build_market_input_from_payload(ingest_payload, ingest_schema)
    market_input_errors = market_structure.validate_market_structure_input(market_input, input_schema)
    if market_input_errors:
        return {
            "status": "invalid_market_input",
            "stage": "market_input_validation",
            "errors": market_input_errors,
            "market_input": market_input,
            "decision_run": None,
        }, 1

    result, exit_code = market_runner.run_market_structure_to_decision(
        market_input=market_input,
        skill=skill,
        input_schema=input_schema,
        feature_schema=feature_schema,
        decision_schema=decision_schema,
        runs_dir=runs_dir,
        paper_trades_log=paper_trades_log,
        decision_log=decision_log,
        trigger=trigger,
        run_label=market_input["meta"].get("source_kind"),
    )
    return {
        "status": "processed" if exit_code == 0 else "error",
        "stage": "decision_complete" if exit_code == 0 else result.get("stage", "decision_error"),
        "errors": result.get("errors", []),
        "market_input": market_input,
        "decision_run": result,
    }, exit_code
