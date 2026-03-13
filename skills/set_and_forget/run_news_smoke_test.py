import argparse
import json
from pathlib import Path

import run_set_and_forget as engine


def evaluate(snapshot: dict):
    skill = engine.load_json(engine.SKILL_FILE)
    schema = engine.load_json(engine.DECISION_SCHEMA_FILE)

    snapshot_errors = engine.validate_snapshot(snapshot, schema)
    if snapshot_errors:
        raise SystemExit(
            json.dumps(
                {
                    "ok": False,
                    "error": "INPUT_SCHEMA_INVALID",
                    "errors": snapshot_errors,
                },
                indent=2,
            )
        )

    result = engine.evaluate_rules(snapshot, skill)
    result = engine.maybe_apply_fxalex_confluence(snapshot, result, skill)
    result = engine.maybe_apply_news_context(snapshot, result, skill)
    unknown_reason_codes = engine.validate_reason_codes(result["reason_codes"], schema)
    if unknown_reason_codes:
        raise SystemExit(
            json.dumps(
                {
                    "ok": False,
                    "error": "OUTPUT_SCHEMA_INVALID",
                    "errors": [f"Unknown reason code: {code}" for code in unknown_reason_codes],
                },
                indent=2,
            )
        )

    return engine.build_payload(snapshot, result)


def build_smoke_report(snapshot_path: Path):
    baseline_snapshot = engine.load_json(snapshot_path)
    baseline_snapshot["news_context_enabled"] = False

    news_snapshot = dict(baseline_snapshot)
    news_snapshot["news_context_enabled"] = True

    baseline = evaluate(baseline_snapshot)
    with_news = evaluate(news_snapshot)
    news_state = with_news["advisory_layers"]["news_context"]

    error_details = {}
    for key in [
        "error_type",
        "error_message",
        "http_status",
        "error_body",
        "env_source_order",
        "env_sources_checked",
        "env_files_loaded",
    ]:
        if key in news_state:
            error_details[key] = news_state[key]

    return {
        "ok": True,
        "pair": with_news["pair"],
        "execution_timeframe": with_news["execution_timeframe"],
        "snapshot_file": str(snapshot_path),
        "baseline": {
            "decision": baseline["decision"],
            "confidence_score": baseline["confidence_score"],
        },
        "with_news": {
            "decision": with_news["decision"],
            "confidence_score": with_news["confidence_score"],
        },
        "changed": {
            "decision_changed": baseline["decision"] != with_news["decision"],
            "confidence_delta": with_news["confidence_score"] - baseline["confidence_score"],
        },
        "news_context": {
            "enabled": news_state["enabled"],
            "used": news_state["used"],
            "impact": news_state["impact"],
            "provider": news_state.get("provider"),
            "api_call_succeeded": news_state.get("api_call_succeeded"),
            "query": news_state.get("query"),
            "reason_codes": news_state["reason_codes"],
            "should_wait": news_state["should_wait"],
            "confidence_penalty": news_state["confidence_penalty"],
            "result_count": news_state.get("result_count"),
            "error_details": error_details,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run a compact Brave news-context smoke test.")
    parser.add_argument("--snapshot-file", type=Path, default=engine.LIVE_SNAPSHOT_FILE)
    args = parser.parse_args()

    report = build_smoke_report(args.snapshot_file)
    json.dump(report, fp=engine.sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
