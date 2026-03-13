from pepperstone_models import PepperstoneOrderRequest, PepperstoneOrderResponse


class NullPepperstoneTransport:
    name = "null_pepperstone_transport"

    def submit_order(self, request: PepperstoneOrderRequest) -> PepperstoneOrderResponse:
        return {
            "ok": False,
            "status": "transport_not_initialized",
            "provider": "pepperstone",
            "provider_order_id": None,
            "provider_raw_status": None,
            "error_code": "transport_not_initialized",
            "error_message": "Null transport cannot submit broker requests.",
        }
