import json
from datetime import datetime, timezone
from pathlib import Path


def build_paper_trade_ticket(snapshot: dict, payload: dict):
    fxalex_state = payload.get("advisory_layers", {}).get("fxalex", {})
    fxalex_used = bool(fxalex_state.get("used", False))
    fxalex_vote_score = fxalex_state.get("vote_score") if fxalex_used else None

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pair": payload["pair"],
        "timeframe": payload["execution_timeframe"],
        "mode": payload["execution_mode"],
        "decision": payload["decision"],
        "entry_price": snapshot.get("entry_price"),
        "stop_loss_price": snapshot.get("stop_loss_price"),
        "take_profit_price": snapshot.get("take_profit_price"),
        "risk_reward_ratio": snapshot["risk_reward_ratio"],
        "planned_risk_percent": snapshot["planned_risk_percent"],
        "confidence_score": payload["confidence_score"],
        "reason_codes": payload["reason_codes"],
        "summary": payload["summary"],
        "fxalex_confluence_used": fxalex_used,
        "fxalex_vote_score": fxalex_vote_score,
        "final_engine_source": "primary_plus_fxalex" if fxalex_used else "primary_only",
    }


def append_jsonl(path: Path, row: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False))
        handle.write("\n")


def should_create_paper_trade(snapshot: dict, payload: dict):
    return snapshot.get("execution_mode") == "paper" and payload["decision"] in ["BUY", "SELL"]


def count_nonempty_jsonl_rows(path: Path):
    if not path.exists():
        return 0

    count = 0
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count
