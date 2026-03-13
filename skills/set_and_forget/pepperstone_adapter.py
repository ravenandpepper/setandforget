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


def build_adapter_output(
    *,
    client_scaffold: dict,
    status: str,
    policy_reason: str | None,
    request_ready: bool,
    prepared_request: dict | None,
    validation_error: str | None = None,
):
    return {
        "adapter": "pepperstone_adapter_v1",
        "status": status,
        "policy_reason": policy_reason,
        "transport_call_allowed": False,
        "configured": client_scaffold["configured"],
        "request_ready": request_ready,
        "transport": client_scaffold["transport"],
        "request_blueprint": client_scaffold["request_blueprint"],
        "missing_required_env_vars": client_scaffold["missing_required_env_vars"],
        "order_intent_validation_errors": client_scaffold["order_intent_validation_errors"],
        "validation_error": validation_error,
        "client_scaffold": client_scaffold,
        "prepared_request": prepared_request,
    }


def evaluate_adapter(base_dir: Path, order_intent: dict, execution_constraints: dict):
    client_scaffold = pepperstone_client.build_client_scaffold(base_dir, order_intent)
    transport_blocked, policy_reason = policy_blocks_transport(execution_constraints)

    if transport_blocked:
        return build_adapter_output(
            client_scaffold=client_scaffold,
            status="blocked_by_policy",
            policy_reason=policy_reason,
            request_ready=False,
            prepared_request=None,
        )

    if not client_scaffold["configured"]:
        return build_adapter_output(
            client_scaffold=client_scaffold,
            status="missing_env",
            policy_reason=None,
            request_ready=False,
            prepared_request=None,
        )

    client = pepperstone_client.build_null_client(base_dir)
    try:
        prepared_request = client.prepare_order(order_intent)
    except ValueError as error:
        return build_adapter_output(
            client_scaffold=client_scaffold,
            status="invalid_order_request",
            policy_reason=None,
            request_ready=False,
            prepared_request=None,
            validation_error=str(error),
        )

    return build_adapter_output(
        client_scaffold=client_scaffold,
        status="prepared_disabled",
        policy_reason=None,
        request_ready=True,
        prepared_request=summarize_prepared_request(prepared_request),
    )
