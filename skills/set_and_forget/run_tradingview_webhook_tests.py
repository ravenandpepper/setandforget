import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import run_set_and_forget as engine
import market_data_fetch
import tradingview_webhook


BASE_DIR = Path(__file__).resolve().parent
FIXTURES_FILE = BASE_DIR / "tradingview_webhook_test_fixtures.json"
WEBHOOK_SCHEMA_FILE = BASE_DIR / "tradingview_webhook_schema.json"
SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"
DECISION_SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"
PROVIDER_FIXTURES_FILE = BASE_DIR / "market_data_fetch_provider_fixtures.json"


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
    def _mock_http_get(url: str, headers: dict | None = None):
        query = parse_qs(urlparse(url).query)
        key = f"{query['symbol'][0]}|{query['interval'][0]}"
        if key not in provider_fixtures["time_series"]:
            raise AssertionError(f"Unexpected provider fixture key: {key}")
        return deepcopy(provider_fixtures["time_series"][key])

    return _mock_http_get


def run_case(case: dict, webhook_schema: dict, skill: dict, decision_schema: dict):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        paper_trades_log = tmp_path / "paper_trades_log.jsonl"
        decision_log = tmp_path / "automation_decisions_log.jsonl"
        runs_dir = tmp_path / "automation_runs"

        provider_fixtures = load_json(PROVIDER_FIXTURES_FILE)
        if case["alert_payload"].get("payload_kind") == "trigger_only":
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
                result, exit_code = tradingview_webhook.run_tradingview_ingest(
                    alert_payload=case["alert_payload"],
                    webhook_schema=webhook_schema,
                    skill=skill,
                    decision_schema=decision_schema,
                    runs_dir=runs_dir,
                    paper_trades_log=paper_trades_log,
                    decision_log=decision_log,
                )
        else:
            result, exit_code = tradingview_webhook.run_tradingview_ingest(
                alert_payload=case["alert_payload"],
                webhook_schema=webhook_schema,
                skill=skill,
                decision_schema=decision_schema,
                runs_dir=runs_dir,
                paper_trades_log=paper_trades_log,
                decision_log=decision_log,
            )

        expected = case["expected"]
        assert exit_code == 0, f"{case['id']}: expected exit_code 0, got {exit_code}"
        assert result["status"] == "processed", f"{case['id']}: alert should be processed"
        assert result["alert_context"]["normalized_pair"] == expected["normalized_pair"], (
            f"{case['id']}: normalized pair mismatch"
        )
        assert result["alert_context"]["normalized_execution_timeframe"] == expected["normalized_execution_timeframe"], (
            f"{case['id']}: normalized timeframe mismatch"
        )
        assert result["automation"]["payload"]["decision"] == expected["decision"], (
            f"{case['id']}: decision mismatch"
        )

        if result["snapshot"] is not None:
            assert result["snapshot"]["pair"] == expected["normalized_pair"], (
                f"{case['id']}: snapshot pair mismatch"
            )
            assert result["snapshot"]["execution_timeframe"] == expected["normalized_execution_timeframe"], (
                f"{case['id']}: snapshot timeframe mismatch"
            )
            validation_errors = engine.validate_snapshot(result["snapshot"], decision_schema)
            assert not validation_errors, f"{case['id']}: mapped snapshot is invalid: {validation_errors}"
        else:
            market_input = result["market_input"]
            assert market_input["meta"]["pair"] == expected["normalized_pair"], (
                f"{case['id']}: market_input pair mismatch"
            )
            assert market_input["meta"]["execution_timeframe"] == expected["normalized_execution_timeframe"], (
                f"{case['id']}: market_input timeframe mismatch"
            )
            if case["alert_payload"].get("payload_kind") == "trigger_only":
                assert result["market_data_fetch"]["status"] == "prepared", (
                    f"{case['id']}: trigger-only flow should prepare market data"
                )
                assert result["market_data_fetch"]["adapter"] == market_data_fetch.TWELVEDATA_ADAPTER_KEY, (
                    f"{case['id']}: trigger-only flow should use the real candle adapter"
                )
                assert result["market_data_fetch"]["fetch_context"]["provider"] == "twelvedata", (
                    f"{case['id']}: trigger-only flow should report Twelve Data as provider"
                )

        decision_rows = load_jsonl(decision_log)
        paper_trade_rows = load_jsonl(paper_trades_log)
        assert len(decision_rows) == 1, f"{case['id']}: expected one automation decision row"
        expected_trigger = "tradingview_trigger_only" if case["alert_payload"].get("payload_kind") == "trigger_only" else "tradingview_webhook"
        assert decision_rows[0]["trigger"] == expected_trigger, (
            f"{case['id']}: trigger mismatch"
        )
        assert decision_rows[0]["decision"] == expected["decision"], (
            f"{case['id']}: decision log mismatch"
        )
        assert decision_rows[0]["paper_trade_created"] == expected["paper_trade_created"], (
            f"{case['id']}: unexpected paper_trade_created value"
        )

        if expected["paper_trade_created"]:
            assert len(paper_trade_rows) == 1, f"{case['id']}: expected one paper trade row"
        else:
            assert len(paper_trade_rows) == 0, f"{case['id']}: unexpected paper trade row"

        return {
            "id": case["id"],
            "decision": result["automation"]["payload"]["decision"],
            "paper_trade_created": expected["paper_trade_created"],
        }


def main():
    fixtures = load_json(FIXTURES_FILE)
    webhook_schema = load_json(WEBHOOK_SCHEMA_FILE)
    skill = load_json(SKILL_FILE)
    decision_schema = load_json(DECISION_SCHEMA_FILE)

    results = []
    for case in fixtures["cases"]:
        results.append(run_case(case, webhook_schema, skill, decision_schema))

    print(f"PASS {len(results)}/{len(fixtures['cases'])} tradingview webhook scenarios")
    for result in results:
        print(
            f"- {result['id']}: decision={result['decision']} "
            f"paper_trade_created={result['paper_trade_created']}"
        )


if __name__ == "__main__":
    main()
