import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SHADOW_TICKETS_FILE = BASE_DIR / "openclaw_shadow_portfolio_log.jsonl"
DEFAULT_SETTLEMENT_LOG_FILE = BASE_DIR / "openclaw_shadow_portfolio_settlements.jsonl"
DEFAULT_TIMEFRAME = "4H"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_json_rows(path: Path):
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if path.suffix == ".json":
        payload = json.loads(text)
        if isinstance(payload, list):
            return payload
        raise ValueError(f"{path} must contain a JSON array")

    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def timestamp_now():
    return datetime.now(UTC).isoformat()


def extract_h4_candles(payload, pair: str | None = None, timeframe: str = DEFAULT_TIMEFRAME):
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        candles = payload.get("candles")
        if isinstance(candles, list):
            return candles
        if isinstance(candles, dict):
            if timeframe.lower() in candles and isinstance(candles[timeframe.lower()], list):
                return candles[timeframe.lower()]
            if timeframe in candles and isinstance(candles[timeframe], list):
                return candles[timeframe]

        markets = payload.get("markets")
        if isinstance(markets, dict):
            if not pair:
                raise ValueError("pair is required when loading candles from a markets fixture")
            market_key = f"{pair}|{timeframe}"
            market = markets.get(market_key)
            if not isinstance(market, dict):
                raise ValueError(f"market fixture does not contain {market_key}")
            market_candles = market.get("candles", {})
            if isinstance(market_candles, dict) and isinstance(market_candles.get("h4"), list):
                return market_candles["h4"]

    raise ValueError("unable to extract H4 candles from the supplied payload")


def price_levels_missing(ticket: dict):
    return (
        ticket.get("entry_price") is None
        or ticket.get("stop_loss_price") is None
        or ticket.get("take_profit_price") is None
    )


def candle_touches_entry(candle: dict, entry_price: float):
    return candle["low"] <= entry_price <= candle["high"]


def evaluate_shadow_ticket(ticket: dict, candles: list[dict]):
    if ticket.get("outcome_status") != "pending":
        return build_settlement_record(ticket, "not_opened", None, None, None, len(candles), None)

    if price_levels_missing(ticket):
        return build_settlement_record(ticket, "price_levels_missing", None, None, None, len(candles), None)

    decision = ticket["decision"]
    entry_price = ticket["entry_price"]
    stop_loss = ticket["stop_loss_price"]
    take_profit = ticket["take_profit_price"]
    entry_triggered_at = None

    for candle in candles:
        high = candle["high"]
        low = candle["low"]

        if decision == "BUY":
            hit_stop = low <= stop_loss
            hit_target = high >= take_profit
            target_price = take_profit
            stop_price = stop_loss
        elif decision == "SELL":
            hit_stop = high >= stop_loss
            hit_target = low <= take_profit
            target_price = take_profit
            stop_price = stop_loss
        else:
            return build_settlement_record(ticket, "not_opened", None, None, None, len(candles), None)

        if entry_triggered_at is None:
            if not candle_touches_entry(candle, entry_price):
                continue
            entry_triggered_at = candle["timestamp"]
            if hit_stop or hit_target:
                return build_settlement_record(
                    ticket,
                    "ambiguous_intrabar",
                    candle["timestamp"],
                    None,
                    None,
                    len(candles),
                    entry_triggered_at,
                )
            continue

        if hit_stop and hit_target:
            return build_settlement_record(
                ticket,
                "ambiguous_intrabar",
                candle["timestamp"],
                None,
                None,
                len(candles),
                entry_triggered_at,
            )
        if hit_target:
            pnl_r = float(ticket["risk_reward_ratio"])
            pnl_percent = round(float(ticket["planned_risk_percent"]) * pnl_r, 4)
            return build_settlement_record(
                ticket,
                "take_profit_hit",
                candle["timestamp"],
                target_price,
                (pnl_r, pnl_percent),
                len(candles),
                entry_triggered_at,
            )
        if hit_stop:
            pnl_r = -1.0
            pnl_percent = round(-float(ticket["planned_risk_percent"]), 4)
            return build_settlement_record(
                ticket,
                "stop_loss_hit",
                candle["timestamp"],
                stop_price,
                (pnl_r, pnl_percent),
                len(candles),
                entry_triggered_at,
            )

    return build_settlement_record(ticket, "pending", None, None, None, len(candles), entry_triggered_at)


def build_settlement_record(
    ticket: dict,
    outcome_status: str,
    closed_at: str | None,
    exit_price: float | None,
    pnl: tuple[float, float] | None,
    candles_evaluated: int,
    entry_triggered_at: str | None,
):
    realized_pnl_r = pnl[0] if pnl else None
    realized_pnl_percent = pnl[1] if pnl else None
    return {
        "shadow_settlement_version": "1.0",
        "settled_at": timestamp_now(),
        "run_id": ticket["run_id"],
        "model_id": ticket["model_id"],
        "portfolio_key": ticket["portfolio_key"],
        "pair": ticket["pair"],
        "execution_timeframe": ticket["execution_timeframe"],
        "decision": ticket["decision"],
        "prior_outcome_status": ticket["outcome_status"],
        "outcome_status": outcome_status,
        "entry_price": ticket.get("entry_price"),
        "entry_triggered_at": entry_triggered_at,
        "exit_price": exit_price,
        "stop_loss_price": ticket.get("stop_loss_price"),
        "take_profit_price": ticket.get("take_profit_price"),
        "risk_reward_ratio": ticket["risk_reward_ratio"],
        "planned_risk_percent": ticket["planned_risk_percent"],
        "realized_pnl_r": realized_pnl_r,
        "realized_pnl_percent": realized_pnl_percent,
        "closed_at": closed_at,
        "candles_evaluated": candles_evaluated,
    }


def run_shadow_portfolio_settlement(
    *,
    shadow_tickets: list[dict],
    candles: list[dict],
    settlement_log: Path,
    settlements_output_file: Path | None = None,
):
    settlements = [evaluate_shadow_ticket(ticket, candles) for ticket in shadow_tickets]
    if settlements_output_file is not None:
        settlements_output_file.write_text(json.dumps(settlements, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    append_jsonl(settlement_log, settlements)

    return {
        "status": "completed",
        "settlement_count": len(settlements),
        "closed_count": sum(1 for item in settlements if item["outcome_status"] in {"take_profit_hit", "stop_loss_hit"}),
        "pending_count": sum(1 for item in settlements if item["outcome_status"] == "pending"),
        "ambiguous_count": sum(1 for item in settlements if item["outcome_status"] == "ambiguous_intrabar"),
        "not_opened_count": sum(1 for item in settlements if item["outcome_status"] == "not_opened"),
        "settlement_log_path": str(settlement_log),
        "settlements_output_file": str(settlements_output_file) if settlements_output_file else None,
        "settlements": settlements,
    }


def main():
    parser = argparse.ArgumentParser(description="Settle pending OpenClaw shadow portfolio tickets against H4 candles.")
    parser.add_argument("--shadow-tickets-file", type=Path, default=DEFAULT_SHADOW_TICKETS_FILE)
    parser.add_argument("--candles-file", type=Path, required=True)
    parser.add_argument("--pair", default=None)
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    parser.add_argument("--settlement-log", type=Path, default=DEFAULT_SETTLEMENT_LOG_FILE)
    parser.add_argument("--settlements-output-file", type=Path, default=None)
    args = parser.parse_args()

    shadow_tickets = load_json_rows(args.shadow_tickets_file)
    candles_payload = load_json(args.candles_file)
    candles = extract_h4_candles(candles_payload, pair=args.pair, timeframe=args.timeframe)
    result = run_shadow_portfolio_settlement(
        shadow_tickets=shadow_tickets,
        candles=candles,
        settlement_log=args.settlement_log,
        settlements_output_file=args.settlements_output_file,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
