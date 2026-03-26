import json
import os
import urllib.parse
import urllib.request


DEFAULT_TELEGRAM_TIMEOUT_SECONDS = 10


def env_flag_enabled(name: str, default: bool = True):
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() not in {"0", "false", "no", "off"}


def build_trade_message(ticket: dict):
    return "\n".join(
        [
            "Set & Forget paper trade geopend",
            f"Pair: {ticket['pair']}",
            f"Timeframe: {ticket['timeframe']}",
            f"Decision: {ticket['decision']}",
            f"Entry: {ticket['entry_price']}",
            f"Stop: {ticket['stop_loss_price']}",
            f"Target: {ticket['take_profit_price']}",
            f"RR: {ticket['risk_reward_ratio']}",
            f"Confidence: {ticket['confidence_score']}",
            f"Reason codes: {', '.join(ticket['reason_codes'])}",
            f"Summary: {ticket['summary']}",
        ]
    )


def send_text_message(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {
            "status": "not_configured",
            "sent": False,
        }

    if not env_flag_enabled("TELEGRAM_TRADE_NOTIFICATIONS_ENABLED", True):
        return {
            "status": "disabled",
            "sent": False,
        }

    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url=f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=DEFAULT_TELEGRAM_TIMEOUT_SECONDS) as response:
        body = json.loads(response.read().decode("utf-8"))

    return {
        "status": "sent",
        "sent": True,
        "telegram_ok": body.get("ok", False),
        "message_id": ((body.get("result") or {}).get("message_id")),
    }


def maybe_send_paper_trade_notification(ticket: dict):
    try:
        return send_text_message(build_trade_message(ticket))
    except Exception as exc:
        return {
            "status": "error",
            "sent": False,
            "error": str(exc),
        }
