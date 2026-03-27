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


def is_actionable_decision(decision: str | None):
    return decision in {"BUY", "SELL"}


def model_label(model_id: str | None):
    token = str(model_id or "").strip()
    if not token:
        return "unknown-model"
    return token.split("/")[-1] or token


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


def build_tournament_report_message(result: dict):
    run = result.get("run") or {}
    primary = result.get("primary_payload") or {}
    entries = result.get("entries") or []
    pair = primary.get("pair") or run.get("pair") or "UNKNOWN"
    timeframe = primary.get("execution_timeframe") or run.get("execution_timeframe") or "UNKNOWN"
    lines = [
        "OpenClaw 4H candle verslag",
        f"Pair: {pair}",
        f"Timeframe: {timeframe}",
        f"Primary: {primary.get('decision', 'UNKNOWN')} ({primary.get('confidence_score', 'n/a')})",
    ]

    if not entries:
        lines.append("Geen modelresultaten beschikbaar voor deze candle.")
        return "\n".join(lines)

    for entry in entries:
        raw_decision = entry.get("model_decision") or entry.get("decision")
        final_decision = entry.get("decision")
        confidence = entry.get("model_confidence_score")
        summary = entry.get("model_summary") or entry.get("summary") or "Geen samenvatting."
        if entry.get("policy_enforced"):
            lines.append(
                (
                    f"{model_label(entry.get('model_id'))}: geen trade; het model wilde wel {raw_decision}, "
                    f"maar de Set & Forget hard gate blokkeerde die. {summary}"
                )
            )
            continue

        trade_state = "trade gemaakt" if is_actionable_decision(final_decision) else "geen trade"
        lines.append(
            f"{model_label(entry.get('model_id'))}: {trade_state} ({final_decision}, confidence {confidence}). {summary}"
        )

    return "\n".join(lines)


def send_text_message(text: str, *, enabled_env_var: str = "TELEGRAM_TRADE_NOTIFICATIONS_ENABLED"):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {
            "status": "not_configured",
            "sent": False,
        }

    if not env_flag_enabled(enabled_env_var, True):
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
        return send_text_message(
            build_trade_message(ticket),
            enabled_env_var="TELEGRAM_TRADE_NOTIFICATIONS_ENABLED",
        )
    except Exception as exc:
        return {
            "status": "error",
            "sent": False,
            "error": str(exc),
        }


def maybe_send_tournament_report_notification(result: dict):
    try:
        return send_text_message(
            build_tournament_report_message(result),
            enabled_env_var="TELEGRAM_TOURNAMENT_REPORTS_ENABLED",
        )
    except Exception as exc:
        return {
            "status": "error",
            "sent": False,
            "error": str(exc),
        }
