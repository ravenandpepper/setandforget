import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SHADOW_TICKETS_FILE = BASE_DIR / "openclaw_shadow_portfolio_log.jsonl"
DEFAULT_SETTLEMENTS_FILE = BASE_DIR / "openclaw_shadow_portfolio_settlements.jsonl"
DEFAULT_REFLECTION_LOG_FILE = BASE_DIR / "openclaw_model_reflection_snapshots.jsonl"
DEFAULT_MODEL_BANKROLL_EUR = 500.0


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


def group_latest_settlements(settlements: list[dict]):
    latest = {}
    for item in settlements:
        key = (item["run_id"], item["model_id"], item["portfolio_key"])
        previous = latest.get(key)
        if previous is None or item.get("settled_at", "") >= previous.get("settled_at", ""):
            latest[key] = item
    return latest


def round_or_none(value, digits=4):
    if value is None:
        return None
    return round(value, digits)


def derive_initial_capital_eur(ticket: dict):
    value = ticket.get("initial_capital_eur")
    if value is None:
        return DEFAULT_MODEL_BANKROLL_EUR
    return float(value)


def derive_realized_pnl_eur(settlement: dict, initial_capital_eur: float):
    if settlement.get("realized_pnl_eur") is not None:
        return float(settlement["realized_pnl_eur"])
    if settlement.get("realized_pnl_percent") is None:
        return None
    return round((initial_capital_eur * float(settlement["realized_pnl_percent"])) / 100.0, 4)


def build_self_review(snapshot: dict):
    points = []
    if snapshot["invalid_output_count"] > 0:
        points.append(
            f"Contract reliability needs work: {snapshot['invalid_output_count']} invalid output events."
        )
    if snapshot["closed_trades_total"] == 0 and snapshot["actionable_trades_total"] == 0:
        points.append("No actionable shadow trades yet; judgement quality is still unproven.")
    elif snapshot["closed_trades_total"] == 0:
        points.append("Actionable trades exist, but none are settled yet; avoid overconfidence.")
    else:
        if snapshot["cumulative_realized_pnl_r"] < 0:
            points.append(
                f"Realized performance is negative at {snapshot['cumulative_realized_pnl_r']}R; tighten selectivity."
            )
        elif snapshot["cumulative_realized_pnl_r"] > 0:
            points.append(
                f"Realized performance is positive at {snapshot['cumulative_realized_pnl_r']}R; preserve what is working."
            )
        else:
            points.append("Realized performance is flat; edge is not demonstrated yet.")

        if snapshot["win_rate_closed_percent"] is not None and snapshot["win_rate_closed_percent"] < 50:
            points.append("Closed-trade win rate is below 50%; be more critical on weak confirmations.")
        elif snapshot["win_rate_closed_percent"] is not None:
            points.append("Closed-trade win rate is acceptable, but sample size still matters.")

    if snapshot["peer_rank_by_pnl"] > 1:
        points.append(
            f"Peer rank is {snapshot['peer_rank_by_pnl']}/{snapshot['peer_count']}; study the better-ranked models."
        )
    else:
        points.append("Current peer rank is strongest by realized R; keep discipline and contract compliance.")

    latest_outcome = snapshot.get("latest_outcome_status")
    if latest_outcome == "stop_loss_hit":
        points.append("Latest settled trade stopped out; reassess timing and confirmation quality.")
    elif latest_outcome == "take_profit_hit":
        points.append("Latest settled trade hit target; verify that the same logic generalizes.")

    return " ".join(points[:3])


def build_model_snapshot(model_id: str, tickets: list[dict], latest_settlement_by_key: dict):
    settlements = []
    invalid_output_count = 0
    total_confidence = 0

    for ticket in tickets:
        total_confidence += ticket["confidence_score"]
        if "OUTPUT_SCHEMA_INVALID" in ticket.get("reason_codes", []):
            invalid_output_count += 1
        key = (ticket["run_id"], ticket["model_id"], ticket["portfolio_key"])
        settlement = latest_settlement_by_key.get(key)
        if settlement is not None:
            settlements.append(settlement)

    actionable_tickets = [ticket for ticket in tickets if ticket.get("shadow_trade_opened")]
    closed = [item for item in settlements if item["outcome_status"] in {"take_profit_hit", "stop_loss_hit"}]
    wins = [item for item in closed if item["outcome_status"] == "take_profit_hit"]
    losses = [item for item in closed if item["outcome_status"] == "stop_loss_hit"]
    pending = [item for item in settlements if item["outcome_status"] == "pending"]
    ambiguous = [item for item in settlements if item["outcome_status"] == "ambiguous_intrabar"]
    not_opened = [item for item in settlements if item["outcome_status"] == "not_opened"]
    initial_capital_eur = derive_initial_capital_eur(max(tickets, key=lambda item: item.get("logged_at", item.get("recorded_at", ""))))
    realized_values = [item["realized_pnl_r"] for item in closed if item["realized_pnl_r"] is not None]
    realized_eur_values = [
        derive_realized_pnl_eur(item, initial_capital_eur)
        for item in closed
        if derive_realized_pnl_eur(item, initial_capital_eur) is not None
    ]
    cumulative_realized_pnl_r = round_or_none(sum(realized_values), 4) if realized_values else 0.0
    cumulative_realized_pnl_eur = round_or_none(sum(realized_eur_values), 4) if realized_eur_values else 0.0
    average_realized_pnl_r = (
        round_or_none(sum(realized_values) / len(realized_values), 4) if realized_values else None
    )
    win_rate_closed_percent = (
        round_or_none((len(wins) / len(closed)) * 100, 2) if closed else None
    )

    latest_ticket = max(tickets, key=lambda item: item.get("logged_at", item.get("recorded_at", "")))
    latest_settlement = (
        max(settlements, key=lambda item: item.get("settled_at", ""))
        if settlements
        else None
    )

    snapshot = {
        "reflection_snapshot_version": "1.0",
        "generated_at": timestamp_now(),
        "model_id": model_id,
        "portfolio_key": latest_ticket["portfolio_key"],
        "portfolio_currency": latest_ticket.get("portfolio_currency", "EUR"),
        "initial_capital_eur": initial_capital_eur,
        "evaluations_total": len(tickets),
        "actionable_trades_total": len(actionable_tickets),
        "closed_trades_total": len(closed),
        "wins_total": len(wins),
        "losses_total": len(losses),
        "pending_trades_total": len(pending),
        "ambiguous_trades_total": len(ambiguous),
        "not_opened_total": len(not_opened),
        "invalid_output_count": invalid_output_count,
        "win_rate_closed_percent": win_rate_closed_percent,
        "cumulative_realized_pnl_r": cumulative_realized_pnl_r,
        "cumulative_realized_pnl_eur": cumulative_realized_pnl_eur,
        "current_equity_eur": round_or_none(
            initial_capital_eur + cumulative_realized_pnl_eur,
            4,
        ),
        "average_realized_pnl_r": average_realized_pnl_r,
        "average_confidence_score": round_or_none(total_confidence / len(tickets), 2) if tickets else None,
        "latest_run_id": latest_ticket["run_id"],
        "latest_decision": latest_ticket["decision"],
        "latest_outcome_status": latest_settlement["outcome_status"] if latest_settlement else None,
        "latest_closed_at": latest_settlement["closed_at"] if latest_settlement else None,
        "latest_reason_codes": latest_ticket["reason_codes"],
    }
    return snapshot


def apply_peer_ranks(snapshots: list[dict]):
    ordered = sorted(
        snapshots,
        key=lambda item: (
            item["invalid_output_count"],
            -(item["cumulative_realized_pnl_r"] or 0.0),
            -(item["actionable_trades_total"] or 0),
            -(item["win_rate_closed_percent"] or -1.0),
            -(item["average_confidence_score"] or 0.0),
            item["model_id"],
        ),
    )
    best_pnl = ordered[0]["cumulative_realized_pnl_r"] if ordered else 0.0
    peer_count = len(ordered)
    for index, item in enumerate(ordered, start=1):
        item["peer_rank_by_pnl"] = index
        item["peer_count"] = peer_count
        pnl_gap = best_pnl - (item["cumulative_realized_pnl_r"] or 0.0)
        item["peer_gap_to_best_r"] = round_or_none(max(0.0, pnl_gap), 4)
        item["self_review"] = build_self_review(item)
    return ordered


def build_reflection_snapshots(tickets: list[dict], settlements: list[dict]):
    latest_settlement_by_key = group_latest_settlements(settlements)
    tickets_by_model = defaultdict(list)
    for ticket in tickets:
        tickets_by_model[ticket["model_id"]].append(ticket)

    snapshots = [
        build_model_snapshot(model_id, model_tickets, latest_settlement_by_key)
        for model_id, model_tickets in sorted(tickets_by_model.items())
    ]
    return apply_peer_ranks(snapshots)


def run_model_reflection_snapshot(
    *,
    tickets: list[dict],
    settlements: list[dict],
    reflection_log: Path,
    output_file: Path | None = None,
):
    snapshots = build_reflection_snapshots(tickets, settlements)
    if output_file is not None:
        output_file.write_text(json.dumps(snapshots, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    append_jsonl(reflection_log, snapshots)
    return {
        "status": "completed",
        "snapshot_count": len(snapshots),
        "reflection_log_path": str(reflection_log),
        "output_file": str(output_file) if output_file else None,
        "snapshots": snapshots,
    }


def main():
    parser = argparse.ArgumentParser(description="Build compact model reflection snapshots from shadow tickets and settlements.")
    parser.add_argument("--shadow-tickets-file", type=Path, default=DEFAULT_SHADOW_TICKETS_FILE)
    parser.add_argument("--settlements-file", type=Path, default=DEFAULT_SETTLEMENTS_FILE)
    parser.add_argument("--reflection-log", type=Path, default=DEFAULT_REFLECTION_LOG_FILE)
    parser.add_argument("--output-file", type=Path, default=None)
    args = parser.parse_args()

    tickets = load_json_rows(args.shadow_tickets_file)
    settlements = load_json_rows(args.settlements_file)
    result = run_model_reflection_snapshot(
        tickets=tickets,
        settlements=settlements,
        reflection_log=args.reflection_log,
        output_file=args.output_file,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
