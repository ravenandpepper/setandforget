import json
import tempfile
from pathlib import Path

import feature_snapshot
import market_structure
import run_set_and_forget as engine


BASE_DIR = Path(__file__).resolve().parent
FIXTURES_FILE = BASE_DIR / "market_structure_test_fixtures.json"
INPUT_SCHEMA_FILE = BASE_DIR / "market_structure_input_schema.json"
FEATURE_SCHEMA_FILE = BASE_DIR / "feature_snapshot_schema.json"
DECISION_SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"
SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def run_case(case: dict, input_schema: dict, feature_schema: dict, decision_schema: dict, skill: dict):
    input_errors = market_structure.validate_market_structure_input(case["market_input"], input_schema)
    assert not input_errors, f"{case['id']}: invalid market input: {input_errors}"

    feature_payload = market_structure.build_feature_snapshot_from_market_input(case["market_input"])
    feature_errors = feature_snapshot.validate_feature_snapshot(feature_payload, feature_schema)
    assert not feature_errors, f"{case['id']}: invalid feature snapshot: {feature_errors}"

    projected_snapshot = feature_snapshot.project_to_decision_snapshot(feature_payload)
    decision_errors = engine.validate_snapshot(projected_snapshot, decision_schema)
    assert not decision_errors, f"{case['id']}: invalid projected snapshot: {decision_errors}"

    expected = case["expected"]
    assert projected_snapshot["weekly_trend"] == expected["weekly_trend"], (
        f"{case['id']}: weekly trend mismatch"
    )
    assert projected_snapshot["daily_trend"] == expected["daily_trend"], (
        f"{case['id']}: daily trend mismatch"
    )

    if "h4_pullback_structure" in expected:
        assert projected_snapshot["h4_pullback_structure"] == expected["h4_pullback_structure"], (
            f"{case['id']}: h4 pullback structure mismatch"
        )
    if "aoi_zone_status" in expected:
        assert projected_snapshot["aoi_zone_status"] == expected["aoi_zone_status"], (
            f"{case['id']}: AOI zone status mismatch"
        )
    if "aoi_confluence_count" in expected:
        assert projected_snapshot["aoi_confluence_count"] == expected["aoi_confluence_count"], (
            f"{case['id']}: AOI confluence count mismatch"
        )
    if "confirmation_type" in expected:
        assert projected_snapshot["confirmation_type"] == expected["confirmation_type"], (
            f"{case['id']}: confirmation type mismatch"
        )
    if "h4_reversal_state" in expected:
        assert projected_snapshot["h4_reversal_state"] == expected["h4_reversal_state"], (
            f"{case['id']}: h4 reversal state mismatch"
        )
    if "first_entry_structure" in expected:
        assert projected_snapshot["first_entry_structure"] == expected["first_entry_structure"], (
            f"{case['id']}: first entry structure mismatch"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        paper_trades_log = Path(tmpdir) / "paper_trades_log.jsonl"
        payload, exit_code = engine.run_decision_cycle(projected_snapshot, skill, decision_schema, paper_trades_log)

    assert exit_code == 0, f"{case['id']}: decision cycle returned non-zero exit code"
    assert payload["decision"] == expected["decision"], (
        f"{case['id']}: expected decision {expected['decision']}, got {payload['decision']}"
    )

    return {
        "id": case["id"],
        "decision": payload["decision"],
        "weekly_trend": projected_snapshot["weekly_trend"],
        "daily_trend": projected_snapshot["daily_trend"],
    }


def assert_confirmation_helper_contracts():
    bullish_retest_candles = [
        {"timestamp": "t1", "open": 1.0960, "high": 1.1000, "low": 1.0940, "close": 1.0990},
        {"timestamp": "t2", "open": 1.0990, "high": 1.1025, "low": 1.0938, "close": 1.1015},
    ]
    bullish_h4_state = {
        "break_of_structure": True,
        "last_confirmed_high": 1.0940,
        "last_confirmed_low": 1.0810,
    }
    assert market_structure.is_bos_retest(bullish_retest_candles, bullish_h4_state, "bullish") is True, (
        "Bullish BOS retest should be detected when price retests and reclaims the broken high"
    )

    hammer_candle = {
        "timestamp": "t3",
        "open": 1.0970,
        "high": 1.1000,
        "low": 1.0870,
        "close": 1.0990,
    }
    assert market_structure.is_hammer(hammer_candle) is True, (
        "Hammer detection should preserve a bullish lower-wick rejection candle"
    )

    shooting_star_candle = {
        "timestamp": "t4",
        "open": 1.0440,
        "high": 1.0500,
        "low": 1.0400,
        "close": 1.0420,
    }
    assert market_structure.is_shooting_star(shooting_star_candle) is True, (
        "Shooting star detection should preserve a bearish upper-wick rejection candle"
    )


def main():
    fixtures = load_json(FIXTURES_FILE)
    input_schema = load_json(INPUT_SCHEMA_FILE)
    feature_schema = load_json(FEATURE_SCHEMA_FILE)
    decision_schema = load_json(DECISION_SCHEMA_FILE)
    skill = load_json(SKILL_FILE)

    results = []
    assert_confirmation_helper_contracts()
    for case in fixtures["cases"]:
        results.append(run_case(case, input_schema, feature_schema, decision_schema, skill))

    print(f"PASS {len(results) + 1}/{len(fixtures['cases']) + 1} market structure scenarios")
    print("- confirmation_helpers_detect_bos_retest_and_rejection_candles: helpers_ok=True")
    for result in results:
        print(
            f"- {result['id']}: decision={result['decision']} "
            f"weekly={result['weekly_trend']} daily={result['daily_trend']}"
        )


if __name__ == "__main__":
    main()
