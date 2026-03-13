from pathlib import Path

import pepperstone_adapter
import pepperstone_config
import runtime_env


BASE_DIR = Path(__file__).resolve().parent
PEPPERSTONE_REQUIRED_ENV_VARS = pepperstone_config.PEPPERSTONE_REQUIRED_ENV_VARS
PEPPERSTONE_OPTIONAL_ENV_VARS = pepperstone_config.PEPPERSTONE_OPTIONAL_ENV_VARS

ACTIONABLE_DECISIONS = {
    "BUY": "buy",
    "SELL": "sell",
}


def build_pepperstone_runtime_config():
    return pepperstone_config.describe_runtime_config(BASE_DIR)


def build_runtime_config():
    env_state = runtime_env.load_standardized_env(BASE_DIR)
    return {
        "env_loading": env_state,
        "providers": {
            "pepperstone": build_pepperstone_runtime_config(),
        },
    }


def build_execution_scaffold(snapshot: dict, payload: dict):
    runtime_config = build_runtime_config()
    base_state = {
        "adapter_version": "execution_scaffold_v1",
        "enabled": False,
        "dry_run": True,
        "paper_only": True,
        "source_of_truth": "set_and_forget",
        "decision_received": payload["decision"],
        "runtime_config": runtime_config,
    }

    if payload["decision"] not in ACTIONABLE_DECISIONS:
        return {
            **base_state,
            "status": "blocked",
            "block_reason": "primary_decision_not_actionable",
            "allowed_decisions": sorted(ACTIONABLE_DECISIONS.keys()),
            "order_intent": None,
            "execution_plan": None,
            "adapters": [],
            "tradingview_contract": None,
            "pepperstone_order_plan": None,
        }

    order_intent = build_order_intent(snapshot, payload)
    adapters = build_adapters(snapshot, payload, order_intent, runtime_config)
    execution_plan = build_execution_plan(order_intent, adapters)

    return {
        **base_state,
        "status": "prepared",
        "block_reason": None,
        "allowed_decisions": sorted(ACTIONABLE_DECISIONS.keys()),
        "order_intent": order_intent,
        "execution_plan": execution_plan,
        "adapters": adapters,
        "tradingview_contract": adapters[0]["contract"],
        "pepperstone_order_plan": adapters[1]["contract"],
    }


def build_order_intent(snapshot: dict, payload: dict):
    return {
        "intent_version": "order_intent_v1",
        "source": payload["primary_strategy"],
        "decision": payload["decision"],
        "side": ACTIONABLE_DECISIONS[payload["decision"]],
        "instrument": payload["pair"],
        "timeframe": payload["execution_timeframe"],
        "execution_mode": payload["execution_mode"],
        "levels": build_levels(snapshot),
        "risk": build_risk(snapshot, payload),
        "context": {
            "confidence_score": payload["confidence_score"],
            "reason_codes": payload["reason_codes"],
            "summary": payload["summary"],
            "advisory_layers": {
                "fxalex": {
                    "used": payload["advisory_layers"]["fxalex"].get("used", False),
                    "impact": payload["advisory_layers"]["fxalex"].get("impact"),
                },
                "news_context": {
                    "used": payload["advisory_layers"]["news_context"].get("used", False),
                    "impact": payload["advisory_layers"]["news_context"].get("impact"),
                },
            },
        },
    }


def build_execution_plan(order_intent: dict, adapters: list):
    return {
        "plan_version": "execution_plan_v1",
        "status": "stubbed",
        "execution_gate": "disabled_dry_run_paper_only",
        "runtime_dependency": "none",
        "live_execution": False,
        "order_intent": order_intent,
        "adapters": adapters,
    }


def build_adapters(snapshot: dict, payload: dict, order_intent: dict, runtime_config: dict):
    return [
        {
            "adapter_key": "tradingview_webhook",
            "adapter_type": "signal_handoff",
            "enabled": False,
            "dry_run": True,
            "paper_only": True,
            "contract": build_tradingview_contract(snapshot, payload, order_intent),
        },
        {
            "adapter_key": "pepperstone",
            "adapter_type": "broker_order_plan",
            "enabled": False,
            "dry_run": True,
            "paper_only": True,
            "contract": build_pepperstone_order_plan(snapshot, payload, order_intent, runtime_config),
        },
    ]


def build_tradingview_contract(snapshot: dict, payload: dict, order_intent: dict):
    return {
        "adapter": "tradingview_webhook_stub",
        "delivery": "disabled",
        "webhook_ready": True,
        "event": "trade_setup_prepared",
        "decision": order_intent["decision"],
        "pair": order_intent["instrument"],
        "timeframe": order_intent["timeframe"],
        "execution_mode": order_intent["execution_mode"],
        "primary_strategy": payload["primary_strategy"],
        "order_intent": order_intent,
        "levels": build_levels(snapshot),
        "risk": build_risk(snapshot, payload),
        "metadata": {
            "confidence_score": payload["confidence_score"],
            "reason_codes": payload["reason_codes"],
            "summary": payload["summary"],
            "fxalex_used": payload["advisory_layers"]["fxalex"].get("used", False),
            "news_context_used": payload["advisory_layers"]["news_context"].get("used", False),
        }
    }


def build_pepperstone_order_plan(snapshot: dict, payload: dict, order_intent: dict, runtime_config: dict):
    execution_constraints = {
        "live_allowed": False,
        "paper_only": True,
        "dry_run": True,
    }
    adapter_state = pepperstone_adapter.evaluate_adapter(
        base_dir=BASE_DIR,
        order_intent=order_intent,
        execution_constraints=execution_constraints,
    )
    request_blueprint = adapter_state["request_blueprint"]
    return {
        "adapter": "pepperstone_order_plan_stub",
        "delivery": "disabled",
        "runtime_dependency": "pepperstone_adapter",
        "intent": "plan_only",
        "side": order_intent["side"],
        "instrument": order_intent["instrument"],
        "timeframe": order_intent["timeframe"],
        "execution_mode": order_intent["execution_mode"],
        "execution_constraints": execution_constraints,
        "order_type": request_blueprint["order_type"],
        "order_intent": order_intent,
        "adapter_state": adapter_state,
        "client_scaffold": adapter_state["client_scaffold"],
        "levels": build_levels(snapshot),
        "risk": build_risk(snapshot, payload),
        "broker_payload": build_pepperstone_broker_payload(request_blueprint),
    }


def build_pepperstone_broker_payload(request_blueprint: dict):
    return {
        "account_id": request_blueprint["account_id"],
        "instrument": request_blueprint["instrument"],
        "side": request_blueprint["side"],
        "order_type": request_blueprint["order_type"],
        "size_units": request_blueprint["size_units"],
        "time_in_force": request_blueprint["time_in_force"],
        "planned_risk_percent": request_blueprint["planned_risk_percent"],
        "stop_loss_price": request_blueprint["stop_loss_price"],
        "take_profit_price": request_blueprint["take_profit_price"],
        "client_order_id": None,
    }


def build_levels(snapshot: dict):
    return {
        "entry_price": snapshot.get("entry_price"),
        "stop_loss_price": snapshot.get("stop_loss_price"),
        "take_profit_price": snapshot.get("take_profit_price"),
        "stop_loss_basis": snapshot.get("stop_loss_basis"),
    }


def build_risk(snapshot: dict, payload: dict):
    return {
        "planned_risk_percent": snapshot["planned_risk_percent"],
        "risk_reward_ratio": snapshot["risk_reward_ratio"],
        "confidence_score": payload["confidence_score"],
    }
