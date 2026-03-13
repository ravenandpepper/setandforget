from pathlib import Path

import pepperstone_client


def policy_blocks_transport(execution_constraints: dict) -> tuple[bool, str | None]:
    if execution_constraints.get("paper_only", True):
        return True, "paper_only"

    if execution_constraints.get("dry_run", True):
        return True, "dry_run"

    if not execution_constraints.get("live_allowed", False):
        return True, "live_not_allowed"

    return False, None


def summarize_prepared_request(request: dict):
    return {
        "instrument": request["instrument"],
        "side": request["side"],
        "order_type": request["order_type"],
        "size_units": request["size_units"],
        "time_in_force": request["time_in_force"],
        "has_stop_loss": request["stop_loss_price"] is not None,
        "has_take_profit": request["take_profit_price"] is not None,
        "client_order_id_present": request["client_order_id"] is not None,
    }


def evaluate_adapter(base_dir: Path, order_intent: dict, execution_constraints: dict):
    client_scaffold = pepperstone_client.build_client_scaffold(base_dir, order_intent)
    transport_blocked, policy_reason = policy_blocks_transport(execution_constraints)

    if transport_blocked:
        return {
            "adapter": "pepperstone_adapter_v1",
            "status": "blocked_by_policy",
            "policy_reason": policy_reason,
            "transport_call_allowed": False,
            "configured": client_scaffold["configured"],
            "request_ready": False,
            "client_scaffold": client_scaffold,
            "prepared_request": None,
        }

    if not client_scaffold["configured"]:
        return {
            "adapter": "pepperstone_adapter_v1",
            "status": "missing_env",
            "policy_reason": None,
            "transport_call_allowed": False,
            "configured": False,
            "request_ready": False,
            "client_scaffold": client_scaffold,
            "prepared_request": None,
        }

    client = pepperstone_client.build_null_client(base_dir)
    try:
        prepared_request = client.prepare_order(order_intent)
    except ValueError as error:
        return {
            "adapter": "pepperstone_adapter_v1",
            "status": "invalid_order_request",
            "policy_reason": None,
            "transport_call_allowed": False,
            "configured": True,
            "request_ready": False,
            "client_scaffold": client_scaffold,
            "prepared_request": None,
            "validation_error": str(error),
        }

    return {
        "adapter": "pepperstone_adapter_v1",
        "status": "prepared_disabled",
        "policy_reason": None,
        "transport_call_allowed": False,
        "configured": True,
        "request_ready": True,
        "client_scaffold": client_scaffold,
        "prepared_request": summarize_prepared_request(prepared_request),
        "transport": client.transport.name,
    }
