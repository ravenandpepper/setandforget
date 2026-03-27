import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import future_execution
import pepperstone_adapter
import pepperstone_client
import pepperstone_client_scaffold
import pepperstone_config
import pepperstone_mapper
import pepperstone_transport
import run_set_and_forget as engine
import runtime_env

BASE_DIR = Path(__file__).resolve().parent
FIXTURES_FILE = BASE_DIR / "execution_scaffolding_test_fixtures.json"
SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"
SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def run_decision(snapshot: dict, skill: dict, schema: dict):
    with tempfile.TemporaryDirectory() as tmpdir:
        paper_trades_log = Path(tmpdir) / "paper_trades_log.jsonl"
        payload, exit_code = engine.run_decision_cycle(snapshot, skill, schema, paper_trades_log)
        assert exit_code == 0, "Decision cycle returned a non-zero exit code"
        assert payload["validation"]["ok"], "Decision payload failed validation"
        return payload


def assert_common_execution_guards(execution_state: dict):
    assert execution_state["enabled"] is False, "Execution scaffold must stay disabled"
    assert execution_state["dry_run"] is True, "Execution scaffold must stay dry-run"
    assert execution_state["paper_only"] is True, "Execution scaffold must stay paper-only"
    env_loading = execution_state["runtime_config"]["env_loading"]
    pepperstone_config = execution_state["runtime_config"]["providers"]["pepperstone"]
    assert env_loading["source_order"] == runtime_env.env_source_order(BASE_DIR), (
        "Execution scaffold must expose the standardized env source order"
    )
    assert env_loading["override_policy"] == "process_env_first_then_setdefault_from_files", (
        "Execution scaffold must preserve process-env precedence"
    )
    expected_files_checked = [
        str(path.expanduser())
        for path in runtime_env.env_file_candidates(BASE_DIR)
    ]
    assert env_loading["files_checked"] == expected_files_checked, (
        "Execution scaffold must check the standardized env file list"
    )
    assert pepperstone_config["adapter_key"] == "pepperstone", (
        "Execution scaffold must expose the Pepperstone adapter config"
    )
    assert pepperstone_config["env_namespace"] == "CTRADER_*", (
        "Pepperstone config must expose the expected cTrader env namespace"
    )
    assert pepperstone_config["required_env_vars"] == future_execution.PEPPERSTONE_REQUIRED_ENV_VARS, (
        "Pepperstone config must expose the required env vars"
    )
    assert pepperstone_config["optional_env_vars"] == future_execution.PEPPERSTONE_OPTIONAL_ENV_VARS, (
        "Pepperstone config must expose the optional env vars"
    )


def assert_pepperstone_env_contract():
    with patch.object(pepperstone_config.runtime_env, "env_file_candidates", return_value=[]):
        with patch.dict(os.environ, {}, clear=True):
            config = pepperstone_config.describe_runtime_config(BASE_DIR)
            assert config["configured"] is False, "Pepperstone config must stay optional when env is absent"
            assert config["present_required_env_vars"] == [], "No required Pepperstone vars should be present"
            assert config["missing_required_env_vars"] == pepperstone_config.PEPPERSTONE_REQUIRED_ENV_VARS, (
                "All required Pepperstone vars should be reported missing when unset"
            )

        with patch.dict(
            os.environ,
            {
                "CTRADER_ENVIRONMENT": "demo",
                "CTRADER_ACCOUNT_ID": "4219358",
                "CTRADER_CLIENT_ID": "demo-client-id",
                "CTRADER_CLIENT_SECRET": "demo-client-secret",
                "CTRADER_REDIRECT_URI": "http://127.0.0.1:8788/callback",
                "CTRADER_AUTH_BASE_URL": "https://openapi.ctrader.com",
                "CTRADER_API_BASE_URL": "https://demo.ctraderapi.com",
            },
            clear=True,
        ):
            config = pepperstone_config.describe_runtime_config(BASE_DIR)
            assert config["configured"] is True, "Pepperstone config must become ready when required env is set"
            assert config["present_required_env_vars"] == pepperstone_config.PEPPERSTONE_REQUIRED_ENV_VARS, (
                "All required Pepperstone vars should be reported present when set"
            )
            assert config["missing_required_env_vars"] == [], (
                "No required Pepperstone vars should remain missing when configured"
            )
            assert config["present_optional_env_vars"] == [
                "CTRADER_AUTH_BASE_URL",
                "CTRADER_API_BASE_URL",
            ], (
                "Optional cTrader base urls should be reported when set"
            )


def assert_pepperstone_client_scaffold_contract():
    order_intent = {
        "instrument": "EURUSD",
        "side": "buy",
        "risk": {
            "planned_risk_percent": 1.0,
        },
        "levels": {
            "stop_loss_price": 1.05,
            "take_profit_price": 1.11,
        },
    }
    with patch.object(pepperstone_config.runtime_env, "env_file_candidates", return_value=[]):
        with patch.dict(os.environ, {}, clear=True):
            missing_env_scaffold = pepperstone_client_scaffold.build_client_scaffold(
                BASE_DIR,
                order_intent,
            )
            assert missing_env_scaffold["status"] == "missing_env", (
                "Client scaffold must report missing env when Pepperstone is unconfigured"
            )
            assert missing_env_scaffold["request_blueprint"]["account_id"] == "from_env", (
                "Client scaffold must keep the account id as an env-backed placeholder"
            )
            assert missing_env_scaffold["transport"] == "null_ctrader_transport", (
                "Client scaffold must expose the null cTrader transport name"
            )
            assert missing_env_scaffold["request_blueprint"]["order_type"] == "market", (
                "Client scaffold must expose the normalized default order type"
            )

    with patch.object(pepperstone_config.runtime_env, "env_file_candidates", return_value=[]):
        with patch.dict(
            os.environ,
            {
                "CTRADER_ENVIRONMENT": "demo",
                "CTRADER_ACCOUNT_ID": "4219358",
                "CTRADER_CLIENT_ID": "demo-client-id",
                "CTRADER_CLIENT_SECRET": "demo-client-secret",
                "CTRADER_REDIRECT_URI": "http://127.0.0.1:8788/callback",
            },
            clear=True,
        ):
            configured_scaffold = pepperstone_client_scaffold.build_client_scaffold(BASE_DIR, order_intent)
            assert configured_scaffold["status"] == "configured_disabled", (
                "Client scaffold must stay disabled even when Pepperstone env is configured"
            )
            assert configured_scaffold["configured"] is True, (
                "Client scaffold must reflect that Pepperstone env is configured"
            )
            assert configured_scaffold["execution_platform"] == "ctrader", (
                "Client scaffold must expose cTrader as the execution platform"
            )
            assert configured_scaffold["prepared_request_ready"] is True, (
                "Client scaffold must mark the prepared request as ready when config is complete"
            )
            assert configured_scaffold["request_blueprint"]["time_in_force"] == "gtc", (
                "Client scaffold must expose the normalized default time in force"
            )


def assert_pepperstone_client_contract():
    order_intent = {
        "instrument": "EURUSD",
        "side": "buy",
        "risk": {
            "planned_risk_percent": 1.0,
        },
        "levels": {
            "stop_loss_price": 1.05,
            "take_profit_price": 1.11,
        },
    }
    with patch.object(pepperstone_config.runtime_env, "env_file_candidates", return_value=[]):
        with patch.dict(
            os.environ,
            {
                "CTRADER_ENVIRONMENT": "demo",
                "CTRADER_ACCOUNT_ID": "4219358",
                "CTRADER_CLIENT_ID": "demo-client-id",
                "CTRADER_CLIENT_SECRET": "demo-client-secret",
                "CTRADER_REDIRECT_URI": "http://127.0.0.1:8788/callback",
            },
            clear=True,
        ):
            client = pepperstone_client.build_null_client(BASE_DIR)
            request = client.prepare_order(order_intent)
            response = client.submit_prepared_order(request)

    assert request["account_id"] == "4219358", (
        "Pepperstone client must map the env-backed account id into the request"
    )
    assert request["instrument"] == "EURUSD", (
        "Pepperstone client must map the order instrument into the request"
    )
    assert request["order_type"] == "market", (
        "Pepperstone client must normalize the order type"
    )
    assert request["time_in_force"] == "gtc", (
        "Pepperstone client must normalize the time in force"
    )
    assert request["size_units"] == "risk_based_position_sizing_pending", (
        "Pepperstone client must expose a stable size placeholder for later sizing logic"
    )
    assert response["status"] == "transport_not_initialized", (
        "Null transport must return a stable disabled response"
    )
    assert response["error_code"] == "transport_not_initialized", (
        "Null transport must expose a stable error code"
    )


def assert_pepperstone_adapter_contract():
    order_intent = {
        "instrument": "EURUSD",
        "side": "buy",
        "risk": {
            "planned_risk_percent": 1.0,
        },
        "levels": {
            "stop_loss_price": 1.05,
            "take_profit_price": 1.11,
        },
    }

    blocked = pepperstone_adapter.evaluate_adapter(
        base_dir=BASE_DIR,
        order_intent=order_intent,
        execution_constraints={
            "live_allowed": False,
            "paper_only": True,
            "dry_run": True,
        },
    )
    assert blocked["status"] == "blocked_by_policy", (
        "Pepperstone adapter must block transport while paper_only is enabled"
    )
    assert blocked["policy_reason"] == "paper_only", (
        "Pepperstone adapter must report the active policy gate"
    )
    assert blocked["request_blueprint"]["instrument"] == "EURUSD", (
        "Pepperstone adapter must always expose the normalized request blueprint"
    )
    assert blocked["prepared_request"] is None, (
        "Pepperstone adapter must not expose a prepared request while policy blocks transport"
    )
    assert blocked["validation_error"] is None, (
        "Pepperstone adapter must keep validation_error empty while policy blocks transport"
    )

    with patch.object(pepperstone_config.runtime_env, "env_file_candidates", return_value=[]):
        with patch.dict(os.environ, {}, clear=True):
            missing_env = pepperstone_adapter.evaluate_adapter(
                base_dir=BASE_DIR,
                order_intent=order_intent,
                execution_constraints={
                    "live_allowed": True,
                    "paper_only": False,
                    "dry_run": False,
                },
            )
            assert missing_env["status"] == "missing_env", (
                "Pepperstone adapter must report missing env when policy allows transport but config is absent"
            )
            assert missing_env["missing_required_env_vars"] == pepperstone_config.PEPPERSTONE_REQUIRED_ENV_VARS, (
                "Pepperstone adapter must expose missing env vars in a stable field"
            )
            assert missing_env["transport"] == "null_ctrader_transport", (
                "Pepperstone adapter must expose the null cTrader transport consistently"
            )

    with patch.object(pepperstone_config.runtime_env, "env_file_candidates", return_value=[]):
        with patch.dict(
            os.environ,
            {
                "CTRADER_ENVIRONMENT": "demo",
                "CTRADER_ACCOUNT_ID": "4219358",
                "CTRADER_CLIENT_ID": "demo-client-id",
                "CTRADER_CLIENT_SECRET": "demo-client-secret",
                "CTRADER_REDIRECT_URI": "http://127.0.0.1:8788/callback",
            },
            clear=True,
        ):
            prepared = pepperstone_adapter.evaluate_adapter(
                base_dir=BASE_DIR,
                order_intent=order_intent,
                execution_constraints={
                    "live_allowed": True,
                    "paper_only": False,
                    "dry_run": False,
                },
            )
            assert prepared["status"] == "prepared_disabled", (
                "Pepperstone adapter must prepare a disabled request when config is present and policy allows it"
            )
            assert prepared["request_ready"] is True, (
                "Pepperstone adapter must mark a valid prepared request as ready"
            )
            assert prepared["prepared_request"]["instrument"] == "EURUSD", (
                "Pepperstone adapter must summarize the prepared instrument"
            )
            assert prepared["prepared_request"]["order_type"] == "market", (
                "Pepperstone adapter must summarize the normalized order type"
            )
            assert prepared["prepared_request"]["time_in_force"] == "gtc", (
                "Pepperstone adapter must summarize the normalized time in force"
            )
            assert prepared["request_blueprint"]["time_in_force"] == "gtc", (
                "Pepperstone adapter must expose the normalized request blueprint directly"
            )
            assert prepared["validation_error"] is None, (
                "Pepperstone adapter must leave validation_error empty for valid requests"
            )

            invalid = pepperstone_adapter.evaluate_adapter(
                base_dir=BASE_DIR,
                order_intent={"instrument": "EURUSD", "side": "hold", "levels": {}, "risk": {}},
                execution_constraints={
                    "live_allowed": True,
                    "paper_only": False,
                    "dry_run": False,
                },
            )
            assert invalid["status"] == "invalid_order_request", (
                "Pepperstone adapter must reject invalid order intents"
            )
            assert invalid["validation_error"] is not None, (
                "Pepperstone adapter must expose a stable validation error field for invalid requests"
            )


def assert_pepperstone_mapper_contract():
    blueprint = pepperstone_mapper.build_request_blueprint({
        "instrument": "EURUSD",
        "side": "buy",
        "risk": {
            "planned_risk_percent": 1.0,
        },
        "levels": {
            "stop_loss_price": 1.05,
            "take_profit_price": 1.11,
        },
    })
    assert blueprint["account_id"] == "from_env", (
        "Pepperstone request blueprint must keep account_id as an env placeholder"
    )
    assert blueprint["order_type"] == "market", (
        "Pepperstone request blueprint must normalize the order type"
    )
    assert blueprint["time_in_force"] == "gtc", (
        "Pepperstone request blueprint must normalize the time in force"
    )
    assert blueprint["size_units"] == "risk_based_position_sizing_pending", (
        "Pepperstone request blueprint must expose the size placeholder"
    )
    assert pepperstone_mapper.validate_order_intent({}) == [
        "instrument_missing",
        "side_invalid",
        "planned_risk_percent_invalid",
        "stop_loss_price_missing",
        "take_profit_price_missing",
    ], (
        "Pepperstone mapper must report missing instrument, side, risk and price levels"
    )
    assert pepperstone_mapper.validate_order_intent(
        {
            "instrument": "EURUSD",
            "side": "buy",
            "risk": {"planned_risk_percent": 1.0},
            "levels": {"stop_loss_price": 1.11, "take_profit_price": 1.05},
        }
    ) == ["price_ladder_invalid_buy"], (
        "Pepperstone mapper must reject invalid buy price ladders"
    )
    assert pepperstone_mapper.validate_order_intent(
        {
            "instrument": "EURUSD",
            "side": "sell",
            "risk": {"planned_risk_percent": 1.0},
            "levels": {"stop_loss_price": 1.05, "take_profit_price": 1.11},
        }
    ) == ["price_ladder_invalid_sell"], (
        "Pepperstone mapper must reject invalid sell price ladders"
    )


def assert_null_transport_contract():
    transport = pepperstone_transport.NullPepperstoneTransport()
    response = transport.submit_order(
        {
            "account_id": "demo-account",
            "instrument": "EURUSD",
            "side": "buy",
            "order_type": "market",
            "size_units": "risk_based_position_sizing_pending",
            "time_in_force": "gtc",
            "stop_loss_price": None,
            "take_profit_price": None,
            "client_order_id": None,
        }
    )
    assert transport.name == "null_ctrader_transport", (
        "Null transport must expose a stable cTrader transport name"
    )
    assert response["provider"] == "ctrader", (
        "Null transport response must identify cTrader as the provider"
    )


def run_prepared_case(case: dict, skill: dict, schema: dict):
    payload = run_decision(case["snapshot"], skill, schema)
    execution_state = payload["future_execution"]
    expected = case["expected"]

    assert payload["decision"] == expected["decision"], (
        f"{case['id']}: expected decision {expected['decision']}, got {payload['decision']}"
    )
    assert execution_state["status"] == expected["status"], (
        f"{case['id']}: expected future_execution status {expected['status']}, got {execution_state['status']}"
    )
    assert_common_execution_guards(execution_state)
    assert execution_state["execution_platform"] == "ctrader", (
        f"{case['id']}: execution scaffold must expose cTrader as the execution platform"
    )
    assert (execution_state["order_intent"] is not None) == expected["order_intent_present"], (
        f"{case['id']}: unexpected order_intent presence"
    )
    assert (execution_state["execution_plan"] is not None) == expected["execution_plan_present"], (
        f"{case['id']}: unexpected execution_plan presence"
    )
    assert len(execution_state["adapters"]) == expected["adapter_count"], (
        f"{case['id']}: unexpected adapter count"
    )
    assert (execution_state["tradingview_contract"] is not None) == expected["tradingview_contract_present"], (
        f"{case['id']}: unexpected TradingView contract presence"
    )
    assert (execution_state["pepperstone_order_plan"] is not None) == expected["pepperstone_order_plan_present"], (
        f"{case['id']}: unexpected Pepperstone plan presence"
    )
    assert execution_state["tradingview_contract"]["delivery"] == "disabled", (
        f"{case['id']}: TradingView delivery must stay disabled"
    )
    assert execution_state["pepperstone_order_plan"]["delivery"] == "disabled", (
        f"{case['id']}: Pepperstone delivery must stay disabled"
    )
    assert execution_state["pepperstone_order_plan"]["runtime_dependency"] == "pepperstone_adapter", (
        f"{case['id']}: Pepperstone runtime dependency must use the adapter layer"
    )
    assert execution_state["pepperstone_order_plan"]["side"] == expected["side"], (
        f"{case['id']}: expected side {expected['side']}, got {execution_state['pepperstone_order_plan']['side']}"
    )
    assert execution_state["pepperstone_order_plan"]["order_type"] == "market", (
        f"{case['id']}: Pepperstone order plan must reuse the normalized order type"
    )
    adapter_state = execution_state["pepperstone_order_plan"]["adapter_state"]
    assert adapter_state["adapter"] == "pepperstone_adapter_v1", (
        f"{case['id']}: Pepperstone adapter id mismatch"
    )
    assert adapter_state["status"] == "blocked_by_policy", (
        f"{case['id']}: Pepperstone adapter must remain blocked by policy in paper mode"
    )
    assert adapter_state["policy_reason"] == "paper_only", (
        f"{case['id']}: Pepperstone adapter must explain the active policy block"
    )
    client_scaffold = execution_state["pepperstone_order_plan"]["client_scaffold"]
    assert client_scaffold["client"] == "pepperstone_client_v1", (
        f"{case['id']}: Pepperstone client id mismatch"
    )
    assert client_scaffold["transport"] == "null_ctrader_transport", (
        f"{case['id']}: Pepperstone scaffold must use the null cTrader transport"
    )
    assert client_scaffold["paper_only"] is True, (
        f"{case['id']}: Pepperstone client scaffold must stay paper-only"
    )
    assert client_scaffold["live_execution"] is False, (
        f"{case['id']}: Pepperstone client scaffold must keep live execution disabled"
    )
    assert client_scaffold["execution_platform"] == "ctrader", (
        f"{case['id']}: Pepperstone client scaffold must expose cTrader as the execution platform"
    )
    assert client_scaffold["request_blueprint"]["instrument"] == payload["pair"], (
        f"{case['id']}: Pepperstone request blueprint instrument mismatch"
    )
    assert client_scaffold["request_blueprint"]["side"] == expected["side"], (
        f"{case['id']}: Pepperstone request blueprint side mismatch"
    )
    assert client_scaffold["request_blueprint"]["order_type"] == "market", (
        f"{case['id']}: Pepperstone request blueprint must normalize order type"
    )
    assert client_scaffold["request_blueprint"]["time_in_force"] == "gtc", (
        f"{case['id']}: Pepperstone request blueprint must normalize time in force"
    )
    assert adapter_state["request_blueprint"] == adapter_state["client_scaffold"]["request_blueprint"], (
        f"{case['id']}: Pepperstone adapter must expose the normalized request blueprint as a top-level field"
    )
    assert adapter_state["transport"] == adapter_state["client_scaffold"]["transport"], (
        f"{case['id']}: Pepperstone adapter must expose the normalized transport as a top-level field"
    )
    assert adapter_state["missing_required_env_vars"] == client_scaffold["missing_required_env_vars"], (
        f"{case['id']}: Pepperstone adapter must expose missing env vars consistently"
    )
    assert adapter_state["order_intent_validation_errors"] == client_scaffold["order_intent_validation_errors"], (
        f"{case['id']}: Pepperstone adapter must expose validation errors consistently"
    )
    assert adapter_state["validation_error"] is None, (
        f"{case['id']}: Pepperstone adapter must keep validation_error empty while blocked by policy"
    )
    assert adapter_state["client_scaffold"] == client_scaffold, (
        f"{case['id']}: Pepperstone adapter must expose the same client scaffold"
    )
    assert adapter_state["transport_call_allowed"] is False, (
        f"{case['id']}: Pepperstone adapter must keep transport disabled"
    )
    assert adapter_state["request_ready"] is False, (
        f"{case['id']}: Pepperstone adapter must not mark requests ready while policy blocks execution"
    )
    broker_payload = execution_state["pepperstone_order_plan"]["broker_payload"]
    assert broker_payload["platform"] == "ctrader", (
        f"{case['id']}: Pepperstone broker payload must mark cTrader as the execution platform"
    )
    assert broker_payload["account_id"] == client_scaffold["request_blueprint"]["account_id"], (
        f"{case['id']}: Pepperstone broker payload must reuse the normalized account reference"
    )
    assert broker_payload["instrument"] == client_scaffold["request_blueprint"]["instrument"], (
        f"{case['id']}: Pepperstone broker payload must reuse the normalized instrument"
    )
    assert broker_payload["side"] == client_scaffold["request_blueprint"]["side"], (
        f"{case['id']}: Pepperstone broker payload must reuse the normalized side"
    )
    assert broker_payload["order_type"] == client_scaffold["request_blueprint"]["order_type"], (
        f"{case['id']}: Pepperstone broker payload must reuse the normalized order type"
    )
    assert broker_payload["size_units"] == client_scaffold["request_blueprint"]["size_units"], (
        f"{case['id']}: Pepperstone broker payload must reuse the normalized size units"
    )
    assert broker_payload["time_in_force"] == client_scaffold["request_blueprint"]["time_in_force"], (
        f"{case['id']}: Pepperstone broker payload must reuse the normalized time in force"
    )
    assert broker_payload["planned_risk_percent"] == client_scaffold["request_blueprint"]["planned_risk_percent"], (
        f"{case['id']}: Pepperstone broker payload must reuse the normalized planned risk"
    )
    assert broker_payload["stop_loss_price"] == client_scaffold["request_blueprint"]["stop_loss_price"], (
        f"{case['id']}: Pepperstone broker payload must reuse the normalized stop loss"
    )
    assert broker_payload["take_profit_price"] == client_scaffold["request_blueprint"]["take_profit_price"], (
        f"{case['id']}: Pepperstone broker payload must reuse the normalized take profit"
    )
    assert broker_payload["client_order_id"] is None, (
        f"{case['id']}: Pepperstone broker payload must keep client_order_id unset"
    )
    assert execution_state["order_intent"]["side"] == expected["side"], (
        f"{case['id']}: order_intent side mismatch"
    )
    assert execution_state["execution_plan"]["execution_gate"] == "disabled_dry_run_paper_only", (
        f"{case['id']}: execution plan gate must stay disabled_dry_run_paper_only"
    )
    for adapter in execution_state["adapters"]:
        assert adapter["enabled"] is False, f"{case['id']}: adapter must stay disabled"
        assert adapter["dry_run"] is True, f"{case['id']}: adapter must stay dry_run"
        assert adapter["paper_only"] is True, f"{case['id']}: adapter must stay paper_only"

    return {
        "id": case["id"],
        "decision": payload["decision"],
        "status": execution_state["status"],
        "side": execution_state["pepperstone_order_plan"]["side"],
    }


def run_blocked_case(case: dict, skill: dict, schema: dict):
    results = []
    for variant in case["variants"]:
        payload = run_decision(variant["snapshot"], skill, schema)
        execution_state = payload["future_execution"]

        assert payload["decision"] == variant["expected_decision"], (
            f"{case['id']}:{variant['label']}: expected decision {variant['expected_decision']}, got {payload['decision']}"
        )
        assert execution_state["status"] == "blocked", (
            f"{case['id']}:{variant['label']}: expected blocked execution state"
        )
        assert_common_execution_guards(execution_state)
        assert execution_state["order_intent"] is None, (
            f"{case['id']}:{variant['label']}: blocked decision should not expose order intent"
        )
        assert execution_state["execution_plan"] is None, (
            f"{case['id']}:{variant['label']}: blocked decision should not expose execution plan"
        )
        assert execution_state["adapters"] == [], (
            f"{case['id']}:{variant['label']}: blocked decision should not expose adapters"
        )
        assert execution_state["tradingview_contract"] is None, (
            f"{case['id']}:{variant['label']}: blocked decision should not expose TradingView contract"
        )
        assert execution_state["pepperstone_order_plan"] is None, (
            f"{case['id']}:{variant['label']}: blocked decision should not expose Pepperstone plan"
        )
        results.append(f"{variant['label']}={payload['decision']}")

    return {
        "id": case["id"],
        "decision": ",".join(results),
        "status": "blocked",
        "side": "not_applicable",
    }


def main():
    fixtures = load_json(FIXTURES_FILE)
    skill = load_json(SKILL_FILE)
    schema = load_json(SCHEMA_FILE)

    assert_pepperstone_env_contract()
    assert_pepperstone_client_scaffold_contract()
    assert_pepperstone_mapper_contract()
    assert_null_transport_contract()
    assert_pepperstone_client_contract()
    assert_pepperstone_adapter_contract()

    results = []
    for case in fixtures["cases"]:
        if "variants" in case:
            results.append(run_blocked_case(case, skill, schema))
        else:
            results.append(run_prepared_case(case, skill, schema))

    print(f"PASS {len(results)}/{len(fixtures['cases'])} execution scaffolding scenarios")
    for result in results:
        print(
            f"- {result['id']}: decision={result['decision']} "
            f"status={result['status']} "
            f"side={result['side']}"
        )


if __name__ == "__main__":
    main()
