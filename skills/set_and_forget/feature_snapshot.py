import json
from pathlib import Path

import run_set_and_forget as engine


BASE_DIR = Path(__file__).resolve().parent
FEATURE_SNAPSHOT_SCHEMA_FILE = BASE_DIR / "feature_snapshot_schema.json"
DECISION_SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def matches_type(value, expected_type):
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def validate_feature_snapshot(feature_snapshot: dict, schema: dict):
    errors = []
    _validate_section(feature_snapshot, schema.get("sections", []), errors, [])
    errors.extend(validate_feature_snapshot_consistency(feature_snapshot))
    return errors


def _validate_section(payload: dict, schema_sections: list, errors: list, path: list):
    for section in schema_sections:
        section_name = section["name"]
        if section_name not in payload:
            errors.append(f"Missing required section: {'.'.join(path + [section_name])}")
            continue

        section_payload = payload[section_name]
        if not isinstance(section_payload, dict):
            errors.append(f"Section {'.'.join(path + [section_name])} must be an object.")
            continue

        for field in section.get("fields", []):
            _validate_field(section_payload, field, errors, path + [section_name])

        if "sections" in section:
            _validate_section(section_payload, section["sections"], errors, path + [section_name])


def _validate_field(section_payload: dict, field: dict, errors: list, path: list):
    name = field["name"]
    dotted = ".".join(path + [name])
    if field.get("required") and name not in section_payload:
        errors.append(f"Missing required field: {dotted}")
        return

    if name not in section_payload:
        return

    value = section_payload[name]
    if value is None and not field.get("required"):
        return

    if not matches_type(value, field["type"]):
        errors.append(f"Field {dotted} must be of type {field['type']}.")
        return

    allowed_values = field.get("allowed_values")
    if allowed_values and value not in allowed_values:
        errors.append(f"Field {dotted} has invalid value {value!r}.")

    field_range = field.get("range")
    if field_range and matches_type(value, "number"):
        lower, upper = field_range
        if value < lower or value > upper:
            errors.append(f"Field {dotted} must be between {lower} and {upper}.")


def validate_feature_snapshot_consistency(feature_snapshot: dict):
    errors = []
    meta = feature_snapshot.get("meta", {})
    aoi = feature_snapshot.get("aoi_features", {})

    if meta.get("objective_only") is not True:
        errors.append("meta.objective_only must be true for this contract.")

    confluence_count = sum(
        1
        for key in ["has_sr", "has_order_block", "has_structural_level"]
        if aoi.get(key) is True
    )
    if "confluence_count" in aoi and aoi["confluence_count"] != confluence_count:
        errors.append("aoi_features.confluence_count must match the AOI confluence booleans.")

    return errors


def project_to_decision_snapshot(feature_snapshot: dict):
    meta = feature_snapshot["meta"]
    timeframes = feature_snapshot["timeframe_features"]
    aoi = feature_snapshot["aoi_features"]
    confirmation = feature_snapshot["confirmation_features"]
    risk = feature_snapshot["risk_features"]
    operational = feature_snapshot["operational_flags"]

    return {
        "pair": meta["pair"],
        "execution_timeframe": meta["execution_timeframe"],
        "execution_mode": meta["execution_mode"],
        "fxalex_confluence_enabled": meta.get("fxalex_confluence_enabled", False),
        "news_context_enabled": meta.get("news_context_enabled", False),
        "weekly_trend": timeframes["weekly"]["trend"],
        "daily_trend": timeframes["daily"]["trend"],
        "h4_pullback_direction": timeframes["h4"]["pullback_direction"],
        "h4_pullback_structure": timeframes["h4"]["pullback_structure"],
        "h4_reversal_state": timeframes["h4"]["reversal_state"],
        "h4_break_of_structure": timeframes["h4"]["break_of_structure"],
        "first_entry_structure": timeframes["h4"]["first_entry_structure"],
        "aoi_zone_status": aoi["zone_status"],
        "aoi_confluence_count": aoi["confluence_count"],
        "aoi_has_sr": aoi["has_sr"],
        "aoi_has_order_block": aoi["has_order_block"],
        "aoi_has_structural_level": aoi["has_structural_level"],
        "confirmation_present": confirmation["present"],
        "confirmation_type": confirmation["type"],
        "stop_loss_basis": risk["stop_loss_basis"],
        "risk_reward_ratio": risk["risk_reward_ratio"],
        "planned_risk_percent": risk["planned_risk_percent"],
        "open_trades_count": operational["open_trades_count"],
        "high_impact_news_imminent": operational["high_impact_news_imminent"],
        "session_window": operational["session_window"],
        "set_and_forget_possible": operational["set_and_forget_possible"],
        "entry_price": risk.get("entry_price"),
        "stop_loss_price": risk.get("stop_loss_price"),
        "take_profit_price": risk.get("take_profit_price"),
        "notes": build_projection_note(feature_snapshot),
    }


def build_projection_note(feature_snapshot: dict):
    meta = feature_snapshot["meta"]
    return (
        f"Projected from feature snapshot v{meta['feature_snapshot_version']} "
        f"from {meta['source_kind']}."
    )


def validate_projected_decision_snapshot(feature_snapshot: dict, decision_schema: dict | None = None):
    decision_schema = decision_schema or load_json(DECISION_SCHEMA_FILE)
    projected_snapshot = project_to_decision_snapshot(feature_snapshot)
    return engine.validate_snapshot(projected_snapshot, decision_schema)


def build_openclaw_evaluation_payload(feature_snapshot: dict, decision_schema: dict | None = None):
    decision_schema = decision_schema or load_json(DECISION_SCHEMA_FILE)
    return {
        "contract_version": "1.0",
        "primary_engine": "set_and_forget",
        "objective_only": True,
        "hard_gate_policy": "primary_hard_gates_non_overridable",
        "feature_snapshot": feature_snapshot,
        "expected_output": decision_schema["expected_output"],
        "advisory_policy": {
            "fxalex": "advisory_only",
            "news_context": "risk_context_only"
        }
    }
