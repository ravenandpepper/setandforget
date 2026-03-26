import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import market_data_fetch
import run_market_data_fetch_schedule_batch as batch_runner
import run_set_and_forget as engine
import tradingview_webhook


BASE_DIR = Path(__file__).resolve().parent
FIXTURES_FILE = BASE_DIR / "market_data_fetch_schedule_batch_test_fixtures.json"
PROVIDER_FIXTURES_FILE = BASE_DIR / "market_data_fetch_provider_fixtures.json"
WEBHOOK_SCHEMA_FILE = BASE_DIR / "tradingview_webhook_schema.json"
SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"
DECISION_SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_mock_http_get(provider_fixtures: dict):
    fallback_by_interval = {}
    for key, payload in provider_fixtures["time_series"].items():
        _, interval = key.split("|", 1)
        fallback_by_interval.setdefault(interval, deepcopy(payload))

    def _mock_http_get(url: str, headers: dict | None = None):
        query = parse_qs(urlparse(url).query)
        key = f"{query['symbol'][0]}|{query['interval'][0]}"
        if key in provider_fixtures["time_series"]:
            return deepcopy(provider_fixtures["time_series"][key])

        interval = query["interval"][0]
        if interval not in fallback_by_interval:
            raise AssertionError(f"Unexpected provider fixture key: {key}")
        return deepcopy(fallback_by_interval[interval])

    return _mock_http_get


def run_case(case: dict, webhook_schema: dict, skill: dict, decision_schema: dict, provider_fixtures: dict):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        paper_trades_log = tmp_path / "paper_trades_log.jsonl"
        decision_log = tmp_path / "automation_decisions_log.jsonl"
        runs_dir = tmp_path / "automation_runs"

        with patch.dict(
            os.environ,
            {
                "TWELVEDATA_API_KEY": "test-api-key",
                "MARKET_DATA_FETCH_ADAPTER": market_data_fetch.TWELVEDATA_ADAPTER_KEY,
            },
            clear=True,
        ), patch.object(
            market_data_fetch.runtime_env,
            "env_file_candidates",
            return_value=[],
        ), patch.object(
            market_data_fetch,
            "perform_http_get_json",
            side_effect=build_mock_http_get(provider_fixtures),
        ):
            summary, exit_code = batch_runner.run_scheduled_trigger_batch(
                webhook_schema=webhook_schema,
                skill=skill,
                decision_schema=decision_schema,
                runs_dir=runs_dir,
                paper_trades_log=paper_trades_log,
                decision_log=decision_log,
                **case["input"],
            )

        expected = case["expected"]
        decision_rows = load_jsonl(decision_log)
        paper_trade_rows = load_jsonl(paper_trades_log)

        assert exit_code == 0, f"{case['id']}: expected exit_code 0, got {exit_code}"
        assert summary["status"] == expected["status"], f"{case['id']}: status mismatch"
        assert summary["total_runs"] == expected["total_runs"], f"{case['id']}: total_runs mismatch"
        assert summary["ok_runs"] == expected["ok_runs"], f"{case['id']}: ok_runs mismatch"
        assert summary["error_runs"] == expected["error_runs"], f"{case['id']}: error_runs mismatch"
        assert len(summary["schedule"]["buckets"]) == expected["bucket_count"], f"{case['id']}: bucket count mismatch"
        assert summary["provider"] == expected["provider"], f"{case['id']}: provider mismatch"
        assert summary["skipped_runs"] == expected["skipped_runs"], f"{case['id']}: skipped_runs mismatch"

        if expected["status"] == "completed":
            assert summary["schedule"]["buckets"][0]["pairs"] == expected["first_bucket_pairs"], (
                f"{case['id']}: first bucket pair order mismatch"
            )
            assert summary["schedule"]["buckets"][1]["pairs"] == expected["second_bucket_pairs"], (
                f"{case['id']}: second bucket pair order mismatch"
            )
            assert len(decision_rows) == expected["total_runs"], f"{case['id']}: decision log row count mismatch"
            assert len(paper_trade_rows) == expected["total_runs"], f"{case['id']}: paper trade row count mismatch"

            for bucket in summary["schedule"]["buckets"]:
                assert bucket["exit_code"] == 0, f"{case['id']}: bucket exit code mismatch"
                for run in bucket["runs"]:
                    assert run["decision"] == expected["decision"], f"{case['id']}: decision mismatch for {run['pair']}"
                    assert run["paper_trade_created"] == expected["paper_trade_created"], (
                        f"{case['id']}: paper trade flag mismatch for {run['pair']}"
                    )
                    assert run["provider"] == expected["provider"], f"{case['id']}: provider mismatch for {run['pair']}"

            for row in decision_rows:
                assert row["trigger"] == "tradingview_trigger_only", f"{case['id']}: trigger mismatch in decision log"
                assert row["decision"] == expected["decision"], f"{case['id']}: decision log mismatch"
        else:
            assert summary["guard"]["skip_reason_code"] == expected["skip_reason_code"], (
                f"{case['id']}: guard reason mismatch"
            )
            assert len(decision_rows) == 0, f"{case['id']}: skipped guard run should not write decisions"
            assert len(paper_trade_rows) == 0, f"{case['id']}: skipped guard run should not write paper trades"

        return {
            "id": case["id"],
            "bucket_count": len(summary["schedule"]["buckets"]),
            "total_runs": summary["total_runs"],
            "status": summary["status"],
        }


def assert_missing_trigger_time_defaults_to_current_utc_minute():
    fixed_trigger_time = datetime(2026, 3, 27, 8, 0, tzinfo=timezone.utc)
    observed = {}

    def fake_run_schedule_plan(plan, webhook_schema, skill, decision_schema, runs_dir, paper_trades_log, decision_log):
        observed["plan"] = plan
        return {
            "provider": plan["provider"],
            "adapter": plan["adapter"],
            "execution_timeframe": plan["execution_timeframe"],
            "execution_mode": plan["execution_mode"],
            "request_budget": plan["request_budget"],
            "schedule": plan["schedule"],
            "total_runs": 0,
            "ok_runs": 0,
            "error_runs": 0,
            "exit_code": 0,
        }, 0

    with patch.object(
        batch_runner.market_data_fetch_schedule,
        "parse_schedule_timestamp",
        return_value=fixed_trigger_time,
    ), patch.object(
        batch_runner,
        "run_schedule_plan",
        side_effect=fake_run_schedule_plan,
    ):
        summary, exit_code = batch_runner.run_scheduled_trigger_batch(
            pairs=["GBPJPY", "EURJPY", "EURGBP"],
            trigger_time=None,
            webhook_schema={},
            skill={},
            decision_schema={},
            runs_dir=BASE_DIR / "tmp_runs",
            paper_trades_log=BASE_DIR / "tmp_paper_trades_log.jsonl",
            decision_log=BASE_DIR / "tmp_automation_decisions_log.jsonl",
        )

    assert exit_code == 0, "trigger_time defaulting exit code mismatch"
    assert summary["status"] == "completed", "trigger_time defaulting status mismatch"
    assert summary["guard"]["eligible"] is True, "trigger_time defaulting guard mismatch"
    assert summary["guard"]["trigger_time"] == "2026-03-27T08:00:00Z", "guard trigger time mismatch"
    assert observed["plan"]["schedule"]["base_trigger_time"] == "2026-03-27T08:00:00Z", "plan trigger time mismatch"
    return {
        "id": "scheduled_trigger_batch_defaults_missing_trigger_time",
        "bucket_count": len(summary["schedule"]["buckets"]),
        "total_runs": summary["total_runs"],
        "status": summary["status"],
    }


def main():
    fixtures = load_json(FIXTURES_FILE)
    provider_fixtures = load_json(PROVIDER_FIXTURES_FILE)
    webhook_schema = tradingview_webhook.load_json(WEBHOOK_SCHEMA_FILE)
    skill = engine.load_json(SKILL_FILE)
    decision_schema = engine.load_json(DECISION_SCHEMA_FILE)

    results = []
    results.append(assert_missing_trigger_time_defaults_to_current_utc_minute())
    for case in fixtures["cases"]:
        results.append(run_case(case, webhook_schema, skill, decision_schema, provider_fixtures))

    print(f"PASS {len(results)}/{len(results)} market data fetch schedule batch scenarios")
    for result in results:
        print(
            f"- {result['id']}: bucket_count={result['bucket_count']} "
            f"total_runs={result['total_runs']} status={result['status']}"
        )


if __name__ == "__main__":
    main()
