import json
from pathlib import Path
from types import SimpleNamespace

import run_set_and_forget as engine

BASE_DIR = Path(__file__).resolve().parent
FIXTURES_FILE = BASE_DIR / "regression_fixtures.json"
SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"
SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def make_fake_fxalex_module(vote_result: dict):
    return SimpleNamespace(
        CLAIMS_FILE=Path("/tmp/fxalex_test_claims.jsonl"),
        load_claims=lambda _path: [],
        vote_claims=lambda _snapshot, _claims, top_n=30: vote_result,
    )


def assert_reason_codes(actual_codes, include=None, exclude=None):
    include = include or []
    exclude = exclude or []

    for code in include:
        assert code in actual_codes, f"Missing reason code: {code}"

    for code in exclude:
        assert code not in actual_codes, f"Unexpected reason code: {code}"


def run_case(case: dict, skill: dict, schema: dict):
    snapshot = case["snapshot"]
    expected = case["expected"]

    validation_errors = engine.validate_snapshot(snapshot, schema)
    assert not validation_errors, f"{case['id']}: invalid fixture: {validation_errors}"

    primary_result = engine.evaluate_rules(snapshot, skill)

    original_loader = engine.load_fxalex_module
    try:
        if case["allow_fxalex_call"]:
            engine.load_fxalex_module = lambda: make_fake_fxalex_module(case["fxalex_vote_result"])
        else:
            def fail_loader():
                raise AssertionError(f"{case['id']}: fxalex layer should not be called for primary decision {primary_result['decision']}")
            engine.load_fxalex_module = fail_loader

        final_result = engine.maybe_apply_fxalex_confluence(snapshot, primary_result, skill)
    finally:
        engine.load_fxalex_module = original_loader

    unknown_reason_codes = engine.validate_reason_codes(final_result["reason_codes"], schema)
    assert not unknown_reason_codes, f"{case['id']}: unknown reason codes: {unknown_reason_codes}"

    assert final_result["decision"] == expected["decision"], (
        f"{case['id']}: expected decision {expected['decision']}, got {final_result['decision']}"
    )
    assert final_result["confidence_score"] == expected["confidence_score"], (
        f"{case['id']}: expected confidence {expected['confidence_score']}, got {final_result['confidence_score']}"
    )

    assert_reason_codes(
        final_result["reason_codes"],
        include=expected.get("reason_codes_include"),
        exclude=expected.get("reason_codes_exclude"),
    )

    fxalex_state = final_result["advisory_layers"]["fxalex"]
    assert fxalex_state["used"] == expected["fxalex_used"], (
        f"{case['id']}: expected fxalex used={expected['fxalex_used']}, got {fxalex_state['used']}"
    )
    assert fxalex_state["impact"] == expected["fxalex_impact"], (
        f"{case['id']}: expected fxalex impact {expected['fxalex_impact']}, got {fxalex_state['impact']}"
    )

    return {
        "id": case["id"],
        "decision": final_result["decision"],
        "confidence_score": final_result["confidence_score"],
        "fxalex_used": fxalex_state["used"],
        "fxalex_impact": fxalex_state["impact"],
    }


def main():
    fixtures = load_json(FIXTURES_FILE)
    skill = load_json(SKILL_FILE)
    schema = load_json(SCHEMA_FILE)

    results = []
    for case in fixtures["cases"]:
        results.append(run_case(case, skill, schema))

    print(f"PASS {len(results)}/{len(fixtures['cases'])} regression scenarios")
    for result in results:
        print(
            f"- {result['id']}: decision={result['decision']} "
            f"confidence={result['confidence_score']} "
            f"fxalex_used={result['fxalex_used']} "
            f"impact={result['fxalex_impact']}"
        )


if __name__ == "__main__":
    main()
