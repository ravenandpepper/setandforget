import json
import tempfile
from pathlib import Path

import model_reflection_snapshot


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


def build_ticket(model_id: str, decision: str, confidence: int, reason_codes: list[str], run_id: str = "run_a"):
    return {
        "shadow_ticket_version": "1.0",
        "logged_at": "2026-03-26T16:14:55.000000+00:00",
        "run_id": run_id,
        "model_id": model_id,
        "portfolio_key": model_id.replace("/", "_"),
        "pair": "EURUSD",
        "execution_timeframe": "4H",
        "execution_mode": "paper",
        "decision": decision,
        "primary_decision": "BUY",
        "entry_price": 1.0862,
        "stop_loss_price": 1.0818,
        "take_profit_price": 1.0968,
        "risk_reward_ratio": 2.4,
        "planned_risk_percent": 1.0,
        "confidence_score": confidence,
        "reason_codes": reason_codes,
        "summary": "fixture",
        "hard_gate_respected": True,
        "policy_enforced": False,
        "shadow_trade_opened": decision in {"BUY", "SELL"},
        "outcome_status": "pending" if decision in {"BUY", "SELL"} else "not_opened",
        "realized_pnl_r": None,
        "realized_pnl_percent": None,
        "closed_at": None,
    }


def build_settlement(model_id: str, outcome_status: str, realized_pnl_r, run_id: str = "run_a"):
    return {
        "shadow_settlement_version": "1.0",
        "settled_at": "2026-03-26T16:41:04.000000+00:00",
        "run_id": run_id,
        "model_id": model_id,
        "portfolio_key": model_id.replace("/", "_"),
        "pair": "EURUSD",
        "execution_timeframe": "4H",
        "decision": "BUY" if outcome_status != "not_opened" else "WAIT",
        "prior_outcome_status": "pending" if outcome_status != "not_opened" else "not_opened",
        "outcome_status": outcome_status,
        "entry_price": 1.0862,
        "entry_triggered_at": "2026-03-10T08:00:00Z" if outcome_status != "not_opened" else None,
        "exit_price": 1.0968 if outcome_status == "take_profit_hit" else 1.0818 if outcome_status == "stop_loss_hit" else None,
        "stop_loss_price": 1.0818,
        "take_profit_price": 1.0968,
        "risk_reward_ratio": 2.4,
        "planned_risk_percent": 1.0,
        "realized_pnl_r": realized_pnl_r,
        "realized_pnl_percent": realized_pnl_r,
        "closed_at": "2026-03-10T20:00:00Z" if outcome_status in {"take_profit_hit", "stop_loss_hit"} else None,
        "candles_evaluated": 9,
    }


def assert_model_snapshot_metrics():
    tickets = [
        build_ticket("openrouter/anthropic/claude-opus-4.6", "BUY", 88, ["HIGHER_TF_ALIGNED", "RR_STRONG"]),
        build_ticket("openrouter/moonshotai/kimi-k2", "WAIT", 0, ["OUTPUT_SCHEMA_INVALID"]),
    ]
    settlements = [
        build_settlement("openrouter/anthropic/claude-opus-4.6", "stop_loss_hit", -1.0),
        build_settlement("openrouter/moonshotai/kimi-k2", "not_opened", None),
    ]

    snapshots = model_reflection_snapshot.build_reflection_snapshots(tickets, settlements)
    opus = next(item for item in snapshots if item["model_id"] == "openrouter/anthropic/claude-opus-4.6")
    kimi = next(item for item in snapshots if item["model_id"] == "openrouter/moonshotai/kimi-k2")

    assert opus["closed_trades_total"] == 1, "Opus should report one closed trade"
    assert opus["cumulative_realized_pnl_r"] == -1.0, "Opus should reflect the realized loss"
    assert opus["win_rate_closed_percent"] == 0.0, "Opus win rate should be 0%"
    assert kimi["invalid_output_count"] == 1, "Kimi should count the schema invalid output"
    assert kimi["actionable_trades_total"] == 0, "Kimi WAIT should not count as actionable"


def assert_peer_ranking_and_self_review():
    tickets = [
        build_ticket("model_a", "BUY", 80, ["HIGHER_TF_ALIGNED"], run_id="run_a"),
        build_ticket("model_b", "BUY", 70, ["HIGHER_TF_ALIGNED"], run_id="run_b"),
        build_ticket("model_c", "WAIT", 0, ["OUTPUT_SCHEMA_INVALID"], run_id="run_c"),
    ]
    settlements = [
        build_settlement("model_a", "take_profit_hit", 2.4, run_id="run_a"),
        build_settlement("model_b", "stop_loss_hit", -1.0, run_id="run_b"),
        build_settlement("model_c", "not_opened", None, run_id="run_c"),
    ]

    snapshots = model_reflection_snapshot.build_reflection_snapshots(tickets, settlements)
    model_a = next(item for item in snapshots if item["model_id"] == "model_a")
    model_b = next(item for item in snapshots if item["model_id"] == "model_b")
    model_c = next(item for item in snapshots if item["model_id"] == "model_c")

    assert model_a["peer_rank_by_pnl"] == 1, "Best realized PnL should rank first"
    assert model_b["peer_rank_by_pnl"] == 2, "Losing model should rank behind the winner"
    assert model_c["peer_rank_by_pnl"] == 3, "Invalid/no-trade model should rank last"
    assert "Contract reliability needs work" in model_c["self_review"], (
        "Self review should call out invalid outputs"
    )
    assert "study the better-ranked models" in model_b["self_review"], (
        "Lower-ranked model should get peer-critical feedback"
    )


def assert_reflection_log_artifacts():
    tickets = [
        build_ticket("model_a", "BUY", 80, ["HIGHER_TF_ALIGNED"], run_id="run_a"),
        build_ticket("model_b", "WAIT", 0, ["OUTPUT_SCHEMA_INVALID"], run_id="run_b"),
    ]
    settlements = [
        build_settlement("model_a", "take_profit_hit", 2.4, run_id="run_a"),
        build_settlement("model_b", "not_opened", None, run_id="run_b"),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        reflection_log = tmp_path / "openclaw_model_reflection_snapshots.jsonl"
        output_file = tmp_path / "model_reflection_snapshot.json"
        result = model_reflection_snapshot.run_model_reflection_snapshot(
            tickets=tickets,
            settlements=settlements,
            reflection_log=reflection_log,
            output_file=output_file,
        )

        rows = load_jsonl(reflection_log)
        assert result["snapshot_count"] == 2, "Expected one reflection snapshot per model"
        assert len(rows) == 2, "Append-only reflection log should contain both snapshots"
        assert output_file.exists(), "Reflection output artifact should be written"


def main():
    assert_model_snapshot_metrics()
    assert_peer_ranking_and_self_review()
    assert_reflection_log_artifacts()

    print("PASS 3/3 model reflection snapshot scenarios")
    print("- model_reflection_aggregates_trade_metrics: metrics_ok=True")
    print("- model_reflection_assigns_peer_ranks_and_self_review: peer_feedback_ok=True")
    print("- model_reflection_writes_append_only_artifacts: artifact_ok=True")


if __name__ == "__main__":
    main()
