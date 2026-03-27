from typing import Protocol, TypedDict


class PepperstoneConfig(TypedDict):
    environment: str | None
    account_id: str | None
    client_id: str | None
    client_secret: str | None
    redirect_uri: str | None
    auth_base_url: str | None
    api_base_url: str | None
    access_token: str | None
    refresh_token: str | None
    token_type: str | None
    access_token_expires_at: str | None
    configured: bool


class PepperstoneRuntimeConfig(TypedDict):
    adapter_key: str
    env_namespace: str
    required_env_vars: list[str]
    optional_env_vars: list[str]
    present_required_env_vars: list[str]
    present_optional_env_vars: list[str]
    missing_required_env_vars: list[str]
    configured: bool


class PepperstoneRequestBlueprint(TypedDict):
    account_id: str
    instrument: str | None
    side: str | None
    order_type: str
    size_units: str
    time_in_force: str
    planned_risk_percent: float | int | None
    stop_loss_price: float | int | None
    take_profit_price: float | int | None


class PepperstoneOrderRequest(TypedDict):
    account_id: str
    instrument: str
    side: str
    order_type: str
    size_units: str | int | float
    time_in_force: str
    stop_loss_price: float | None
    take_profit_price: float | None
    client_order_id: str | None


class PepperstoneOrderResponse(TypedDict):
    ok: bool
    status: str
    provider: str
    provider_order_id: str | None
    provider_raw_status: str | None
    error_code: str | None
    error_message: str | None


class PepperstoneTransport(Protocol):
    name: str

    def submit_order(self, request: PepperstoneOrderRequest) -> PepperstoneOrderResponse:
        ...
