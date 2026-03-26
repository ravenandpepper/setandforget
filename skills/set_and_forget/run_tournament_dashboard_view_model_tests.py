import json
import sys
import tempfile
from pathlib import Path

import tournament_dashboard_view_model


def build_tournament_row(
    model_id: str,
    decision: str,
    confidence_score: int,
    recorded_at: str,
    run_id: str,
    reason_codes: list[str],
    primary_decision: str = "BUY",
):
    return {
        "tournament_entry_version": "1.0",
        "recorded_at": recorded_at,
        "run_id": run_id,
        "model_id": model_id,
        "adapter": "openrouter",
        "pair": "EURUSD",
        "execution_timeframe": "4H",
        "decision": decision,
        "confidence_score": confidence_score,
        "reason_codes": reason_codes,
        "summary": "fixture",
        "primary_decision": primary_decision,
        "hard_gate_respected": True,
        "policy_enforced": False,
        "objective_only": True,
    }


def build_settlement_row(
    model_id: str,
    run_id: str,
    outcome_status: str,
    realized_pnl_r,
    settled_at: str,
):
    return {
        "shadow_settlement_version": "1.0",
        "settled_at": settled_at,
        "run_id": run_id,
        "model_id": model_id,
        "portfolio_key": model_id.replace("/", "_"),
        "pair": "EURUSD",
        "execution_timeframe": "4H",
        "decision": "BUY",
        "prior_outcome_status": "pending",
        "outcome_status": outcome_status,
        "entry_price": 1.0862,
        "entry_triggered_at": "2026-03-10T08:00:00Z",
        "exit_price": 1.0968 if outcome_status == "take_profit_hit" else 1.0818,
        "stop_loss_price": 1.0818,
        "take_profit_price": 1.0968,
        "risk_reward_ratio": 2.4,
        "planned_risk_percent": 1.0,
        "realized_pnl_r": realized_pnl_r,
        "realized_pnl_percent": realized_pnl_r,
        "closed_at": "2026-03-10T20:00:00Z",
        "candles_evaluated": 9,
    }


def build_reflection_row(
    model_id: str,
    generated_at: str,
    peer_rank_by_pnl: int,
    peer_gap_to_best_r: float,
    self_review: str,
):
    return {
        "reflection_snapshot_version": "1.0",
        "generated_at": generated_at,
        "model_id": model_id,
        "peer_rank_by_pnl": peer_rank_by_pnl,
        "peer_gap_to_best_r": peer_gap_to_best_r,
        "self_review": self_review,
    }


def assert_dashboard_view_model_aggregates_metrics():
    tournament_rows = [
        build_tournament_row(
            "openrouter/anthropic/claude-opus-4.6",
            "BUY",
            82,
            "2026-03-26T16:00:00+00:00",
            "run_a",
            ["HIGHER_TF_ALIGNED"],
        ),
        build_tournament_row(
            "openrouter/anthropic/claude-opus-4.6",
            "BUY",
            75,
            "2026-03-26T17:00:00+00:00",
            "run_b",
            ["HIGHER_TF_ALIGNED"],
        ),
        build_tournament_row(
            "openrouter/moonshotai/kimi-k2",
            "WAIT",
            0,
            "2026-03-26T16:05:00+00:00",
            "run_a",
            ["OUTPUT_SCHEMA_INVALID"],
        ),
        build_tournament_row(
            "openrouter/moonshotai/kimi-k2",
            "BUY",
            63,
            "2026-03-26T17:05:00+00:00",
            "run_b",
            ["HIGHER_TF_ALIGNED"],
        ),
    ]
    settlement_rows = [
        build_settlement_row(
            "openrouter/anthropic/claude-opus-4.6",
            "run_a",
            "take_profit_hit",
            2.4,
            "2026-03-26T18:00:00+00:00",
        ),
        build_settlement_row(
            "openrouter/anthropic/claude-opus-4.6",
            "run_b",
            "stop_loss_hit",
            -1.0,
            "2026-03-26T19:00:00+00:00",
        ),
        build_settlement_row(
            "openrouter/moonshotai/kimi-k2",
            "run_b",
            "take_profit_hit",
            2.4,
            "2026-03-26T19:05:00+00:00",
        ),
    ]
    reflection_rows = [
        build_reflection_row(
            "openrouter/anthropic/claude-opus-4.6",
            "2026-03-26T19:10:00+00:00",
            2,
            1.0,
            "Tighten selectivity after the last stop-out.",
        ),
        build_reflection_row(
            "openrouter/moonshotai/kimi-k2",
            "2026-03-26T18:30:00+00:00",
            4,
            3.4,
            "Older reflection should be ignored.",
        ),
        build_reflection_row(
            "openrouter/moonshotai/kimi-k2",
            "2026-03-26T19:20:00+00:00",
            1,
            0.0,
            "Contract reliability improved in the latest run.",
        ),
    ]

    result = tournament_dashboard_view_model.build_dashboard_view_model(
        tournament_rows,
        settlement_rows,
        reflection_rows,
    )

    assert result["overview"]["model_count"] == 2, "Expected one leaderboard row per model"
    assert result["overview"]["tournament_entry_count"] == 4, "Overview should count all tournament rows"
    assert result["overview"]["settlement_count"] == 3, "Overview should count all settlement rows"
    assert result["leaderboard"][0]["model_id"] == "openrouter/moonshotai/kimi-k2", (
        "Kimi should rank first on higher cumulative realized R once valid"
    )
    assert result["leaderboard"][0]["peer_rank_by_pnl"] == 1, (
        "Latest reflection snapshot should feed through to the leaderboard"
    )
    assert result["leaderboard"][0]["invalid_output_count"] == 1, (
        "Invalid outputs should still be visible on the leaderboard"
    )
    assert result["leaderboard"][1]["cumulative_realized_pnl_r"] == 1.4, (
        "Opus cumulative realized R should sum across closed trades"
    )
    assert result["leaderboard"][1]["baseline_agreement_rate_percent"] == 100.0, (
        "Agreement with the primary baseline should be surfaced"
    )
    assert result["leaderboard"][1]["equity_curve"][-1]["equity_r"] == 1.4, (
        "Equity curve should carry cumulative realized R over time"
    )
    assert result["charts"]["performance_bars"][0]["model_id"] == "openrouter/moonshotai/kimi-k2", (
        "Performance bars should follow leaderboard ordering"
    )


def assert_dashboard_recent_decisions_and_output_file():
    tournament_rows = [
        build_tournament_row(
            "model_a",
            "BUY",
            61,
            "2026-03-26T16:00:00+00:00",
            "run_a",
            ["HIGHER_TF_ALIGNED"],
        ),
        build_tournament_row(
            "model_b",
            "WAIT",
            0,
            "2026-03-26T16:10:00+00:00",
            "run_b",
            ["PULLBACK_NOT_PRESENT"],
            primary_decision="WAIT",
        ),
        build_tournament_row(
            "model_c",
            "SELL",
            58,
            "2026-03-26T16:20:00+00:00",
            "run_c",
            ["HIGHER_TF_ALIGNED"],
            primary_decision="SELL",
        ),
    ]
    result = tournament_dashboard_view_model.build_dashboard_view_model(
        tournament_rows,
        settlement_rows=[],
        reflection_rows=[],
        recent_limit=2,
    )

    assert len(result["recent_decisions"]) == 2, "Recent decisions should respect the configured limit"
    assert result["recent_decisions"][0]["run_id"] == "run_c", (
        "Recent decisions should be returned newest-first"
    )
    assert result["recent_decisions"][1]["run_id"] == "run_b", (
        "Second-most-recent decision should be preserved"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        tournament_log = tmp_path / "openclaw_tournament_log.jsonl"
        settlement_log = tmp_path / "openclaw_shadow_portfolio_settlements.jsonl"
        reflection_log = tmp_path / "openclaw_model_reflection_snapshots.jsonl"
        output_file = tmp_path / "openclaw_tournament_dashboard_view_model.json"
        tournament_log.write_text(
            "".join(json.dumps(row) + "\n" for row in tournament_rows),
            encoding="utf-8",
        )
        settlement_log.write_text("", encoding="utf-8")
        reflection_log.write_text("", encoding="utf-8")

        args = [
            "tournament_dashboard_view_model.py",
            "--tournament-log",
            str(tournament_log),
            "--settlement-log",
            str(settlement_log),
            "--reflection-log",
            str(reflection_log),
            "--output-file",
            str(output_file),
        ]
        saved_argv = sys.argv
        sys.argv = args
        try:
            exit_code = tournament_dashboard_view_model.main()
        finally:
            sys.argv = saved_argv

        assert exit_code == 0, "CLI entrypoint should exit cleanly"
        payload = json.loads(output_file.read_text(encoding="utf-8"))
        assert payload["overview"]["model_count"] == 3, "CLI should write the built dashboard payload"


def main():
    assert_dashboard_view_model_aggregates_metrics()
    assert_dashboard_recent_decisions_and_output_file()

    print("PASS 2/2 tournament dashboard view model scenarios")
    print("- tournament_dashboard_view_model_aggregates_leaderboard_and_charts: metrics_ok=True")
    print("- tournament_dashboard_view_model_writes_recent_decisions_artifact: artifact_ok=True")


if __name__ == "__main__":
    main()
