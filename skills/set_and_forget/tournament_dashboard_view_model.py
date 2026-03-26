import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TOURNAMENT_LOG_FILE = BASE_DIR / "openclaw_tournament_log.jsonl"
DEFAULT_SETTLEMENT_LOG_FILE = BASE_DIR / "openclaw_shadow_portfolio_settlements.jsonl"
DEFAULT_REFLECTION_LOG_FILE = BASE_DIR / "openclaw_model_reflection_snapshots.jsonl"
DEFAULT_OUTPUT_FILE = BASE_DIR / "openclaw_tournament_dashboard_view_model.json"


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


def timestamp_now():
    return datetime.now(UTC).isoformat()


def round_or_none(value, digits=4):
    if value is None:
        return None
    return round(value, digits)


def sort_by_time(rows: list[dict], field: str):
    return sorted(rows, key=lambda item: (item.get(field, ""), item.get("run_id", ""), item.get("model_id", "")))


def latest_by_model(rows: list[dict], timestamp_field: str):
    latest = {}
    for row in rows:
        model_id = row.get("model_id")
        if not isinstance(model_id, str):
            continue
        previous = latest.get(model_id)
        if previous is None or row.get(timestamp_field, "") >= previous.get(timestamp_field, ""):
            latest[model_id] = row
    return latest


def build_settlement_index(settlements: list[dict]):
    latest = {}
    for row in settlements:
        key = (row.get("run_id"), row.get("model_id"))
        previous = latest.get(key)
        if previous is None or row.get("settled_at", "") >= previous.get("settled_at", ""):
            latest[key] = row
    return latest


def calculate_model_metrics(model_id: str, entries: list[dict], settlement_index: dict, latest_reflection: dict | None):
    ordered_entries = sort_by_time(entries, "recorded_at")
    invalid_output_count = sum(1 for item in ordered_entries if "OUTPUT_SCHEMA_INVALID" in item.get("reason_codes", []))
    actionable_entries = [item for item in ordered_entries if item["decision"] in {"BUY", "SELL"}]
    baseline_agreement_count = sum(1 for item in ordered_entries if item["decision"] == item["primary_decision"])
    cumulative_r = 0.0
    equity_curve = []
    recent_outcomes = []
    wins = 0
    losses = 0
    closed = 0

    for item in ordered_entries:
        settlement = settlement_index.get((item["run_id"], item["model_id"]))
        outcome_status = settlement.get("outcome_status") if settlement else None
        realized_r = settlement.get("realized_pnl_r") if settlement else None
        if outcome_status in {"take_profit_hit", "stop_loss_hit"} and realized_r is not None:
            cumulative_r += realized_r
            closed += 1
            if outcome_status == "take_profit_hit":
                wins += 1
            else:
                losses += 1

        equity_curve.append(
            {
                "run_id": item["run_id"],
                "recorded_at": item["recorded_at"],
                "equity_r": round_or_none(cumulative_r, 4),
                "decision": item["decision"],
                "outcome_status": outcome_status or "unsettled",
            }
        )
        recent_outcomes.append(
            {
                "run_id": item["run_id"],
                "decision": item["decision"],
                "confidence_score": item["confidence_score"],
                "outcome_status": outcome_status or "unsettled",
                "realized_pnl_r": realized_r,
                "recorded_at": item["recorded_at"],
            }
        )

    avg_confidence = round_or_none(
        sum(item["confidence_score"] for item in ordered_entries) / len(ordered_entries),
        2,
    ) if ordered_entries else None
    win_rate = round_or_none((wins / closed) * 100, 2) if closed else None
    agreement_rate = round_or_none((baseline_agreement_count / len(ordered_entries)) * 100, 2) if ordered_entries else None
    latest_entry = ordered_entries[-1] if ordered_entries else None

    latest_outcome = recent_outcomes[-1] if recent_outcomes else None
    return {
        "model_id": model_id,
        "display_name": model_id.split("/")[-1],
        "evaluations_total": len(ordered_entries),
        "actionable_total": len(actionable_entries),
        "closed_total": closed,
        "wins_total": wins,
        "losses_total": losses,
        "invalid_output_count": invalid_output_count,
        "baseline_agreement_rate_percent": agreement_rate,
        "win_rate_percent": win_rate,
        "cumulative_realized_pnl_r": round_or_none(cumulative_r, 4),
        "average_confidence_score": avg_confidence,
        "latest_decision": latest_entry["decision"] if latest_entry else None,
        "latest_confidence_score": latest_entry["confidence_score"] if latest_entry else None,
        "latest_outcome_status": latest_outcome["outcome_status"] if latest_outcome else None,
        "latest_recorded_at": latest_entry["recorded_at"] if latest_entry else None,
        "peer_rank_by_pnl": latest_reflection.get("peer_rank_by_pnl") if latest_reflection else None,
        "peer_gap_to_best_r": latest_reflection.get("peer_gap_to_best_r") if latest_reflection else None,
        "self_review": latest_reflection.get("self_review") if latest_reflection else None,
        "equity_curve": equity_curve,
        "recent_outcomes": recent_outcomes[-5:],
    }


def sort_leaderboard(items: list[dict]):
    return sorted(
        items,
        key=lambda item: (
            item["peer_rank_by_pnl"] is None,
            item["peer_rank_by_pnl"] or 999999,
            item["invalid_output_count"],
            -(item["cumulative_realized_pnl_r"] or 0.0),
            -(item["baseline_agreement_rate_percent"] or 0.0),
            -(item["average_confidence_score"] or 0.0),
            item["model_id"],
        ),
    )


def build_dashboard_view_model(
    tournament_rows: list[dict],
    settlement_rows: list[dict],
    reflection_rows: list[dict],
    *,
    recent_limit: int = 12,
):
    settlement_index = build_settlement_index(settlement_rows)
    latest_reflection_by_model = latest_by_model(reflection_rows, "generated_at")
    rows_by_model = defaultdict(list)
    for row in tournament_rows:
        rows_by_model[row["model_id"]].append(row)

    leaderboard = [
        calculate_model_metrics(
            model_id,
            rows_by_model[model_id],
            settlement_index,
            latest_reflection_by_model.get(model_id),
        )
        for model_id in sorted(rows_by_model.keys())
    ]
    leaderboard = sort_leaderboard(leaderboard)
    for index, item in enumerate(leaderboard, start=1):
        item["leaderboard_rank"] = index

    recent_decisions = sort_by_time(tournament_rows, "recorded_at")[-recent_limit:]
    recent_decisions.reverse()

    equity_curves = [
        {
            "model_id": item["model_id"],
            "display_name": item["display_name"],
            "points": item["equity_curve"],
        }
        for item in leaderboard
    ]
    performance_bars = [
        {
            "model_id": item["model_id"],
            "display_name": item["display_name"],
            "cumulative_realized_pnl_r": item["cumulative_realized_pnl_r"],
            "win_rate_percent": item["win_rate_percent"],
            "invalid_output_count": item["invalid_output_count"],
            "baseline_agreement_rate_percent": item["baseline_agreement_rate_percent"],
        }
        for item in leaderboard
    ]

    return {
        "view_model_version": "1.0",
        "generated_at": timestamp_now(),
        "overview": {
            "model_count": len(leaderboard),
            "tournament_entry_count": len(tournament_rows),
            "settlement_count": len(settlement_rows),
            "reflection_snapshot_count": len(reflection_rows),
        },
        "leaderboard": leaderboard,
        "charts": {
            "equity_curves": equity_curves,
            "performance_bars": performance_bars,
        },
        "recent_decisions": recent_decisions,
    }


def main():
    parser = argparse.ArgumentParser(description="Build a compact dashboard view model from tournament, settlement, and reflection logs.")
    parser.add_argument("--tournament-log", type=Path, default=DEFAULT_TOURNAMENT_LOG_FILE)
    parser.add_argument("--settlement-log", type=Path, default=DEFAULT_SETTLEMENT_LOG_FILE)
    parser.add_argument("--reflection-log", type=Path, default=DEFAULT_REFLECTION_LOG_FILE)
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args()

    tournament_rows = load_json_rows(args.tournament_log)
    settlement_rows = load_json_rows(args.settlement_log)
    reflection_rows = load_json_rows(args.reflection_log)
    result = build_dashboard_view_model(tournament_rows, settlement_rows, reflection_rows)
    args.output_file.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
