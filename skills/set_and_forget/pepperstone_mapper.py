from pepperstone_models import PepperstoneConfig, PepperstoneOrderRequest, PepperstoneRequestBlueprint


DEFAULT_ORDER_TYPE = "market"
DEFAULT_TIME_IN_FORCE = "gtc"
DEFAULT_SIZE_UNITS = "risk_based_position_sizing_pending"


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def determine_order_type(order_intent: dict) -> str:
    levels = order_intent.get("levels", {})
    entry_price = levels.get("entry_price")
    if is_number(entry_price):
        return "market"
    return DEFAULT_ORDER_TYPE


def determine_time_in_force(order_intent: dict) -> str:
    return DEFAULT_TIME_IN_FORCE


def determine_size_units(order_intent: dict) -> str:
    risk = order_intent.get("risk", {})
    planned_risk_percent = risk.get("planned_risk_percent")
    if is_number(planned_risk_percent) and planned_risk_percent > 0:
        return DEFAULT_SIZE_UNITS
    return "risk_missing"


def validate_order_intent(order_intent: dict) -> list[str]:
    errors = []
    levels = order_intent.get("levels", {})
    risk = order_intent.get("risk", {})

    if not order_intent.get("instrument"):
        errors.append("instrument_missing")

    if order_intent.get("side") not in {"buy", "sell"}:
        errors.append("side_invalid")

    if not is_number(risk.get("planned_risk_percent")) or risk.get("planned_risk_percent") <= 0:
        errors.append("planned_risk_percent_invalid")

    stop_loss_price = levels.get("stop_loss_price")
    take_profit_price = levels.get("take_profit_price")
    if not is_number(stop_loss_price):
        errors.append("stop_loss_price_missing")
    if not is_number(take_profit_price):
        errors.append("take_profit_price_missing")

    if is_number(stop_loss_price) and is_number(take_profit_price):
        side = order_intent.get("side")
        if side == "buy":
            if stop_loss_price >= take_profit_price:
                errors.append("price_ladder_invalid_buy")
        elif side == "sell":
            if stop_loss_price <= take_profit_price:
                errors.append("price_ladder_invalid_sell")

    return errors


def build_request_blueprint(order_intent: dict) -> PepperstoneRequestBlueprint:
    levels = order_intent.get("levels", {})
    risk = order_intent.get("risk", {})
    return {
        "account_id": "from_env",
        "instrument": order_intent.get("instrument"),
        "side": order_intent.get("side"),
        "order_type": determine_order_type(order_intent),
        "size_units": determine_size_units(order_intent),
        "time_in_force": determine_time_in_force(order_intent),
        "planned_risk_percent": risk.get("planned_risk_percent"),
        "stop_loss_price": levels.get("stop_loss_price"),
        "take_profit_price": levels.get("take_profit_price"),
    }


def build_order_request(order_intent: dict, config: PepperstoneConfig) -> PepperstoneOrderRequest:
    validation_errors = validate_order_intent(order_intent)
    if validation_errors:
        raise ValueError(", ".join(validation_errors))

    levels = order_intent.get("levels", {})
    account_id = config.get("account_id")
    if not account_id:
        raise ValueError("account_id_missing")

    return {
        "account_id": account_id,
        "instrument": order_intent["instrument"],
        "side": order_intent["side"],
        "order_type": determine_order_type(order_intent),
        "size_units": determine_size_units(order_intent),
        "time_in_force": determine_time_in_force(order_intent),
        "stop_loss_price": levels.get("stop_loss_price"),
        "take_profit_price": levels.get("take_profit_price"),
        "client_order_id": None,
    }
