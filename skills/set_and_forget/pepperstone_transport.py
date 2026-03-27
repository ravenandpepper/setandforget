from pepperstone_models import PepperstoneOrderRequest, PepperstoneOrderResponse


class NullPepperstoneTransport:
    name = "null_ctrader_transport"

    def submit_order(self, request: PepperstoneOrderRequest) -> PepperstoneOrderResponse:
        return {
            "ok": False,
            "status": "transport_not_initialized",
            "provider": "ctrader",
            "provider_order_id": None,
            "provider_raw_status": None,
            "error_code": "transport_not_initialized",
            "error_message": "Null cTrader transport cannot submit broker requests.",
        }
