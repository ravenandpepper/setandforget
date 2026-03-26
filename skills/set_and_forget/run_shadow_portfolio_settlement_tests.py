import json
import tempfile
from pathlib import Path

import shadow_portfolio_settlement


BASE_DIR = Path(__file__).resolve().parent
MARKET_FIXTURES_FILE = BASE_DIR / "market_data_fetch_fixtures.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_shadow_ticket(model_id: str, decision: str, outcome_status: str = "pending"):
    stop_loss_price = 1.0818
    take_profit_price = 1.0968
    if decision == "SELL":
        stop_loss_price = 1.0968
        take_profit_price = 1.0818

    return {
        "run_id": "test_run",
        "model_id": model_id,
        "portfolio_key": model_id.replace("/", "_"),
        "pair": "EURUSD",
        "execution_timeframe": "4H",
        "execution_mode": "paper",
        "decision": decision,
        "primary_decision": "BUY",
        "entry_price": 1.0862,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "risk_reward_ratio": 2.4,
        "planned_risk_percent": 1.0,
        "confidence_score": 80,
        "reason_codes": ["HIGHER_TF_ALIGNED"],
        "summary": "fixture",
        "hard_gate_respected": True,
        "policy_enforced": False,
        "shadow_trade_opened": decision in {"BUY", "SELL"},
        "outcome_status": outcome_status,
        "realized_pnl_r": None,
        "realized_pnl_percent": None,
        "closed_at": None,
    }


def assert_extract_h4_candles_contract():
    payload = load_json(MARKET_FIXTURES_FILE)
    candles = shadow_portfolio_settlement.extract_h4_candles(payload, pair="EURUSD", timeframe="4H")
    assert len(candles) == 9, "fixture scaffold should expose 9 H4 candles"
    assert candles[-1]["timestamp"] == "2026-03-11T08:00:00Z", "expected final H4 candle timestamp"


def assert_buy_stop_loss_settlement_in_fixture_window():
    payload = load_json(MARKET_FIXTURES_FILE)
    candles = shadow_portfolio_settlement.extract_h4_candles(payload, pair="EURUSD", timeframe="4H")
    ticket = build_shadow_ticket("openrouter/anthropic/claude-opus-4.6", "BUY")

    settlement = shadow_portfolio_settlement.evaluate_shadow_ticket(ticket, candles)
    assert settlement["outcome_status"] == "stop_loss_hit", "fixture BUY should stop out in the outcome window"
    assert settlement["realized_pnl_r"] == -1.0, "stopped BUY should realize -1R"
    assert settlement["realized_pnl_percent"] == -1.0, "stopped BUY should realize -risk percent"
    assert settlement["closed_at"] == "2026-03-10T20:00:00Z", "expected H4 candle to stop the trade"


def assert_buy_take_profit_settlement_in_synthetic_window():
    candles = [
        {"timestamp": "2026-03-11T00:00:00Z", "open": 1.0900, "high": 1.0920, "low": 1.0850, "close": 1.0880},
        {"timestamp": "2026-03-11T04:00:00Z", "open": 1.0880, "high": 1.0980, "low": 1.0860, "close": 1.0970},
    ]
    ticket = build_shadow_ticket("openrouter/anthropic/claude-sonnet-4.6", "BUY")

    settlement = shadow_portfolio_settlement.evaluate_shadow_ticket(ticket, candles)
    assert settlement["outcome_status"] == "take_profit_hit", "synthetic BUY should hit take profit"
    assert settlement["realized_pnl_r"] == 2.4, "take profit should realize configured RR"
    assert settlement["realized_pnl_percent"] == 2.4, "take profit should realize RR times risk percent"
    assert settlement["closed_at"] == "2026-03-11T04:00:00Z", "expected synthetic H4 candle to close the trade"


def assert_wait_ticket_stays_not_opened():
    payload = load_json(MARKET_FIXTURES_FILE)
    candles = shadow_portfolio_settlement.extract_h4_candles(payload, pair="EURUSD", timeframe="4H")
    ticket = build_shadow_ticket("openrouter/moonshotai/kimi-k2", "WAIT", outcome_status="not_opened")

    settlement = shadow_portfolio_settlement.evaluate_shadow_ticket(ticket, candles)
    assert settlement["outcome_status"] == "not_opened", "WAIT ticket must remain not_opened"
    assert settlement["realized_pnl_r"] is None, "WAIT ticket should not realize PnL"


def assert_batch_settlement_logs_records():
    payload = load_json(MARKET_FIXTURES_FILE)
    candles = shadow_portfolio_settlement.extract_h4_candles(payload, pair="EURUSD", timeframe="4H")
    tickets = [
        build_shadow_ticket("openrouter/anthropic/claude-opus-4.6", "BUY"),
        build_shadow_ticket("openrouter/minimax/minimax-m1", "SELL"),
        build_shadow_ticket("openrouter/moonshotai/kimi-k2", "WAIT", outcome_status="not_opened"),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        settlement_log = tmp_path / "openclaw_shadow_portfolio_settlements.jsonl"
        settlements_output = tmp_path / "shadow_portfolio_settlements.json"
        result = shadow_portfolio_settlement.run_shadow_portfolio_settlement(
            shadow_tickets=tickets,
            candles=candles,
            settlement_log=settlement_log,
            settlements_output_file=settlements_output,
        )

        rows = load_jsonl(settlement_log)
        assert result["settlement_count"] == 3, "expected one settlement row per ticket"
        assert result["closed_count"] == 2, "BUY and SELL fixture tickets should both close"
        assert result["not_opened_count"] == 1, "WAIT ticket should remain not_opened"
        assert len(rows) == 3, "append-only settlement log should contain all rows"
        assert settlements_output.exists(), "settlement artifact must be written"
        sell_row = next(item for item in rows if item["decision"] == "SELL")
        assert sell_row["outcome_status"] == "take_profit_hit", "fixture SELL should hit take profit"
        assert sell_row["realized_pnl_r"] == 2.4, "profitable SELL should realize configured RR"


def main():
    assert_extract_h4_candles_contract()
    assert_buy_stop_loss_settlement_in_fixture_window()
    assert_buy_take_profit_settlement_in_synthetic_window()
    assert_wait_ticket_stays_not_opened()
    assert_batch_settlement_logs_records()

    print("PASS 5/5 shadow portfolio settlement scenarios")
    print("- market_fixture_extracts_h4_outcome_window: candles=9")
    print("- buy_shadow_ticket_stops_out_in_fixture_window: outcome_status=stop_loss_hit")
    print("- buy_shadow_ticket_hits_take_profit_in_synthetic_window: outcome_status=take_profit_hit")
    print("- wait_shadow_ticket_remains_not_opened: outcome_status=not_opened")
    print("- batch_shadow_settlement_logs_append_only_rows: closed_count=2")


if __name__ == "__main__":
    main()
