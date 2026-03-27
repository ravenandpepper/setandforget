from pathlib import Path

import pepperstone_config
import pepperstone_mapper
import pepperstone_transport
from pepperstone_models import PepperstoneConfig, PepperstoneOrderRequest, PepperstoneOrderResponse


class PepperstoneClient:
    def __init__(self, config: PepperstoneConfig, transport):
        self.config = config
        self.transport = transport

    def prepare_order(self, order_intent: dict) -> PepperstoneOrderRequest:
        return pepperstone_mapper.build_order_request(order_intent, self.config)

    def submit_prepared_order(self, request: PepperstoneOrderRequest) -> PepperstoneOrderResponse:
        return self.transport.submit_order(request)


def build_null_client(base_dir: Path) -> PepperstoneClient:
    return PepperstoneClient(
        config=pepperstone_config.load_config(base_dir),
        transport=pepperstone_transport.NullPepperstoneTransport(),
    )


def build_client_scaffold(base_dir: Path, order_intent: dict):
    runtime_config = pepperstone_config.describe_runtime_config(base_dir)
    client = build_null_client(base_dir)
    request_blueprint = pepperstone_mapper.build_request_blueprint(order_intent)
    validation_errors = pepperstone_mapper.validate_order_intent(order_intent)

    status = "configured_disabled" if runtime_config["configured"] else "missing_env"
    prepared_request_ready = runtime_config["configured"] and not validation_errors
    if validation_errors:
        status = "invalid_order_request"

    return {
        "client": "pepperstone_client_v1",
        "status": status,
        "configured": runtime_config["configured"],
        "transport": client.transport.name,
        "paper_only": True,
        "live_execution": False,
        "execution_platform": "ctrader",
        "account_environment": client.config["environment"],
        "runtime_config": runtime_config,
        "required_env_vars": runtime_config["required_env_vars"],
        "missing_required_env_vars": runtime_config["missing_required_env_vars"],
        "order_intent_validation_errors": validation_errors,
        "prepared_request_ready": prepared_request_ready,
        "request_blueprint": request_blueprint,
        "next_step": "Exchange the cTrader app credentials for OAuth tokens before enabling transport.",
    }
