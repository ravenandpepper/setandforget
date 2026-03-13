import json
import tempfile
from pathlib import Path

import market_data_ingest
import run_set_and_forget as engine


BASE_DIR = Path(__file__).resolve().parent
EXAMPLE_FILE = BASE_DIR / "market_data_ingest.example.json"
INGEST_SCHEMA_FILE = BASE_DIR / "market_data_ingest_schema.json"
INPUT_SCHEMA_FILE = BASE_DIR / "market_structure_input_schema.json"
FEATURE_SCHEMA_FILE = BASE_DIR / "feature_snapshot_schema.json"
DECISION_SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"
SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def run_valid_case():
    payload = load_json(EXAMPLE_FILE)
    ingest_schema = load_json(INGEST_SCHEMA_FILE)
    input_schema = load_json(INPUT_SCHEMA_FILE)
    feature_schema = load_json(FEATURE_SCHEMA_FILE)
    decision_schema = load_json(DECISION_SCHEMA_FILE)
    skill = load_json(SKILL_FILE)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        result, exit_code = market_data_ingest.run_market_data_ingest(
            ingest_payload=payload,
            ingest_schema=ingest_schema,
            input_schema=input_schema,
            feature_schema=feature_schema,
            skill=skill,
            decision_schema=decision_schema,
            runs_dir=tmp_path / "automation_runs",
            paper_trades_log=tmp_path / "paper_trades_log.jsonl",
            decision_log=tmp_path / "automation_decisions_log.jsonl",
        )

    assert exit_code == 0, "valid ingest should succeed"
    assert result["status"] == "processed", "valid ingest should be processed"
    assert result["market_input"]["meta"]["pair"] == "EURUSD", "pair should be normalized"
    assert result["market_input"]["meta"]["execution_timeframe"] == "4H", "timeframe should be normalized"
    assert result["decision_run"]["automation"]["payload"]["decision"] == "BUY", "example payload should produce BUY"
    return {
        "id": "example_candle_bundle_processed",
        "decision": result["decision_run"]["automation"]["payload"]["decision"],
        "paper_trade_created": result["decision_run"]["automation"]["run"]["paper_trade_created"],
    }


def run_invalid_case():
    payload = {
        "pair": "EURUSD",
        "execution_timeframe": "4H",
        "candles": {
            "weekly": [],
            "daily": []
        },
        "risk_features": {
            "stop_loss_basis": "last_swing",
            "risk_reward_ratio": 2.0,
            "planned_risk_percent": 1.0
        },
        "operational_flags": {
            "open_trades_count": 0,
            "high_impact_news_imminent": False,
            "session_window": "london_newyork_overlap",
            "set_and_forget_possible": True
        }
    }
    ingest_schema = load_json(INGEST_SCHEMA_FILE)
    input_schema = load_json(INPUT_SCHEMA_FILE)
    feature_schema = load_json(FEATURE_SCHEMA_FILE)
    decision_schema = load_json(DECISION_SCHEMA_FILE)
    skill = load_json(SKILL_FILE)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        result, exit_code = market_data_ingest.run_market_data_ingest(
            ingest_payload=payload,
            ingest_schema=ingest_schema,
            input_schema=input_schema,
            feature_schema=feature_schema,
            skill=skill,
            decision_schema=decision_schema,
            runs_dir=tmp_path / "automation_runs",
            paper_trades_log=tmp_path / "paper_trades_log.jsonl",
            decision_log=tmp_path / "automation_decisions_log.jsonl",
        )

    assert exit_code == 1, "invalid ingest should fail"
    assert result["status"] == "invalid_ingest_payload", "invalid ingest should fail at ingest validation"
    assert result["stage"] == "ingest_payload_validation", "invalid ingest should report ingest validation stage"
    assert result["errors"], "invalid ingest should report errors"
    return {"id": "invalid_candle_bundle_rejected", "stage": result["stage"]}


def main():
    valid = run_valid_case()
    invalid = run_invalid_case()
    print("PASS 2/2 market data ingest scenarios")
    print(
        f"- {valid['id']}: decision={valid['decision']} "
        f"paper_trade_created={valid['paper_trade_created']}"
    )
    print(f"- {invalid['id']}: stage={invalid['stage']}")


if __name__ == "__main__":
    main()
