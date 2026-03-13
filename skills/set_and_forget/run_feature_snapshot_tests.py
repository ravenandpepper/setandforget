import json
from pathlib import Path

import feature_snapshot


BASE_DIR = Path(__file__).resolve().parent
FEATURE_SNAPSHOT_FILE = BASE_DIR / "feature_snapshot.example.json"
FEATURE_SCHEMA_FILE = BASE_DIR / "feature_snapshot_schema.json"
DECISION_SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def assert_feature_snapshot_contract():
    feature_payload = load_json(FEATURE_SNAPSHOT_FILE)
    feature_schema = load_json(FEATURE_SCHEMA_FILE)
    decision_schema = load_json(DECISION_SCHEMA_FILE)

    feature_errors = feature_snapshot.validate_feature_snapshot(feature_payload, feature_schema)
    assert not feature_errors, f"Feature snapshot validation failed: {feature_errors}"

    projected = feature_snapshot.project_to_decision_snapshot(feature_payload)
    decision_errors = feature_snapshot.validate_projected_decision_snapshot(feature_payload, decision_schema)
    assert not decision_errors, f"Projected decision snapshot is invalid: {decision_errors}"

    assert projected["weekly_trend"] == feature_payload["timeframe_features"]["weekly"]["trend"], (
        "Projected weekly trend must reuse the feature snapshot trend"
    )
    assert projected["daily_trend"] == feature_payload["timeframe_features"]["daily"]["trend"], (
        "Projected daily trend must reuse the feature snapshot trend"
    )
    assert projected["h4_break_of_structure"] == feature_payload["timeframe_features"]["h4"]["break_of_structure"], (
        "Projected BOS must reuse the feature snapshot BOS state"
    )
    assert projected["aoi_confluence_count"] == feature_payload["aoi_features"]["confluence_count"], (
        "Projected AOI confluence count must reuse the feature snapshot AOI count"
    )
    assert projected["confirmation_type"] == feature_payload["confirmation_features"]["type"], (
        "Projected confirmation type must reuse the feature snapshot confirmation"
    )
    assert projected["risk_reward_ratio"] == feature_payload["risk_features"]["risk_reward_ratio"], (
        "Projected RR must reuse the feature snapshot RR"
    )
    assert projected["notes"].startswith("Projected from feature snapshot"), (
        "Projected decision snapshot must annotate its source"
    )


def assert_openclaw_payload_contract():
    feature_payload = load_json(FEATURE_SNAPSHOT_FILE)
    decision_schema = load_json(DECISION_SCHEMA_FILE)

    evaluation_payload = feature_snapshot.build_openclaw_evaluation_payload(feature_payload, decision_schema)
    expected_output = decision_schema["expected_output"]

    assert evaluation_payload["primary_engine"] == "set_and_forget", (
        "OpenClaw payload must expose the primary engine id"
    )
    assert evaluation_payload["objective_only"] is True, (
        "OpenClaw payload must stay objective-only"
    )
    assert evaluation_payload["hard_gate_policy"] == "primary_hard_gates_non_overridable", (
        "OpenClaw payload must preserve hard-gate policy"
    )
    assert evaluation_payload["feature_snapshot"] == feature_payload, (
        "OpenClaw payload must embed the full objective feature snapshot"
    )
    assert evaluation_payload["expected_output"] == expected_output, (
        "OpenClaw payload must expose the existing decision output contract"
    )
    assert evaluation_payload["advisory_policy"]["fxalex"] == "advisory_only", (
        "OpenClaw payload must preserve fxalex as advisory-only"
    )


def main():
    assert_feature_snapshot_contract()
    assert_openclaw_payload_contract()

    print("PASS 2/2 feature snapshot scenarios")
    print("- feature_snapshot_projects_cleanly_into_decision_snapshot: projected_snapshot_valid=True")
    print("- openclaw_payload_remains_objective_only: hard_gate_policy=primary_hard_gates_non_overridable")


if __name__ == "__main__":
    main()
