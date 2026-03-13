import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import paper_trading
import run_set_and_forget as engine

BASE_DIR = Path(__file__).resolve().parent
FIXTURES_FILE = BASE_DIR / "paper_trade_test_fixtures.json"
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


def load_jsonl_rows(path: Path):
    rows = []
    if not path.exists():
        return rows

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_payload_for_snapshot(snapshot: dict, skill: dict, schema: dict, allow_fxalex_call: bool, fxalex_vote_result=None):
    validation_errors = engine.validate_snapshot(snapshot, schema)
    assert not validation_errors, f"Invalid fixture snapshot: {validation_errors}"

    primary_result = engine.evaluate_rules(snapshot, skill)
    original_loader = engine.load_fxalex_module
    try:
        if allow_fxalex_call:
            engine.load_fxalex_module = lambda: make_fake_fxalex_module(fxalex_vote_result)
        else:
            def fail_loader():
                raise AssertionError(f"fxalex should not be called for primary decision {primary_result['decision']}")
            engine.load_fxalex_module = fail_loader

        result = engine.maybe_apply_fxalex_confluence(snapshot, primary_result, skill)
    finally:
        engine.load_fxalex_module = original_loader

    unknown_reason_codes = engine.validate_reason_codes(result["reason_codes"], schema)
    assert not unknown_reason_codes, f"Unknown reason codes: {unknown_reason_codes}"
    return engine.build_payload(snapshot, result)


def write_ticket_if_needed(snapshot: dict, payload: dict, log_path: Path):
    if not paper_trading.should_create_paper_trade(snapshot, payload):
        return None

    ticket = paper_trading.build_paper_trade_ticket(snapshot, payload)
    paper_trading.append_jsonl(log_path, ticket)
    return ticket


def run_single_ticket_case(case: dict, skill: dict, schema: dict):
    snapshot = case["snapshot"]
    expected = case["expected"]

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "paper_trades_log.jsonl"
        payload = build_payload_for_snapshot(
            snapshot,
            skill,
            schema,
            allow_fxalex_call=case["allow_fxalex_call"],
            fxalex_vote_result=case.get("fxalex_vote_result"),
        )
        ticket = write_ticket_if_needed(snapshot, payload, log_path)
        rows = load_jsonl_rows(log_path)

    assert payload["decision"] == expected["decision"], (
        f"{case['id']}: expected decision {expected['decision']}, got {payload['decision']}"
    )
    assert (ticket is not None) == expected["paper_trade_created"], (
        f"{case['id']}: unexpected paper_trade_created value"
    )
    assert len(rows) == expected["logged_rows"], (
        f"{case['id']}: expected {expected['logged_rows']} logged rows, got {len(rows)}"
    )
    assert rows[0]["fxalex_confluence_used"] == expected["fxalex_confluence_used"], (
        f"{case['id']}: fxalex_confluence_used mismatch"
    )
    assert rows[0]["fxalex_vote_score"] == expected["fxalex_vote_score"], (
        f"{case['id']}: fxalex_vote_score mismatch"
    )
    assert rows[0]["final_engine_source"] == expected["final_engine_source"], (
        f"{case['id']}: final_engine_source mismatch"
    )

    return {
        "id": case["id"],
        "decision": payload["decision"],
        "logged_rows": len(rows),
        "final_engine_source": rows[0]["final_engine_source"],
    }


def run_blocked_case(case: dict, skill: dict, schema: dict):
    results = []
    for variant in case["variants"]:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "paper_trades_log.jsonl"
            payload = build_payload_for_snapshot(
                variant["snapshot"],
                skill,
                schema,
                allow_fxalex_call=variant["allow_fxalex_call"],
            )
            ticket = write_ticket_if_needed(variant["snapshot"], payload, log_path)
            rows = load_jsonl_rows(log_path)

        assert payload["decision"] == variant["expected_decision"], (
            f"{case['id']}:{variant['label']}: expected decision {variant['expected_decision']}, got {payload['decision']}"
        )
        assert ticket is None, f"{case['id']}:{variant['label']}: blocked decision created a paper trade"
        assert len(rows) == 0, f"{case['id']}:{variant['label']}: blocked decision wrote to the paper log"
        results.append(f"{variant['label']}={payload['decision']}")

    return {
        "id": case["id"],
        "decision": ",".join(results),
        "logged_rows": 0,
        "final_engine_source": "not_applicable",
    }


def main():
    fixtures = load_json(FIXTURES_FILE)
    skill = load_json(SKILL_FILE)
    schema = load_json(SCHEMA_FILE)

    results = []
    for case in fixtures["cases"]:
        if "variants" in case:
            results.append(run_blocked_case(case, skill, schema))
        else:
            results.append(run_single_ticket_case(case, skill, schema))

    print(f"PASS {len(results)}/{len(fixtures['cases'])} paper trade scenarios")
    for result in results:
        print(
            f"- {result['id']}: decision={result['decision']} "
            f"logged_rows={result['logged_rows']} "
            f"engine_source={result['final_engine_source']}"
        )


if __name__ == "__main__":
    main()
