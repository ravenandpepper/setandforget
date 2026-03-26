import argparse
import json
import subprocess
import sys
from pathlib import Path

import run_scheduled_market_watch as market_watch
import run_set_and_forget as engine
import run_structured_automation as automation


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = BASE_DIR / "scheduled_market_watch.json"
DEFAULT_TIMER_UNIT = "setandforget-market-watch.timer"
DEFAULT_SERVICE_UNIT = "setandforget-market-watch.service"


def load_last_jsonl_row(path: Path):
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as handle:
        rows = [line.strip() for line in handle if line.strip()]
    if not rows:
        return None
    return json.loads(rows[-1])


def count_jsonl_rows(path: Path):
    if not path.exists():
        return 0

    count = 0
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def parse_systemctl_show_output(text: str):
    payload = {}
    for line in text.splitlines():
        if not line.strip() or "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key] = value
    return payload


def run_command(args: list[str]):
    try:
        completed = subprocess.run(args, capture_output=True, text=True, check=False)
    except FileNotFoundError as error:
        return {
            "ok": False,
            "returncode": 127,
            "stdout": "",
            "stderr": str(error),
        }

    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def read_unit_show(unit_name: str):
    result = run_command(
        [
            "systemctl",
            "--user",
            "show",
            unit_name,
            "--property=Id,ActiveState,SubState,UnitFileState,NextElapseUSecRealtime,LastTriggerUSec,Result",
        ]
    )
    if not result["ok"]:
        return {
            "available": False,
            "error": result["stderr"].strip() or result["stdout"].strip() or f"systemctl exited with {result['returncode']}",
        }
    payload = parse_systemctl_show_output(result["stdout"])
    payload["available"] = True
    return payload


def read_recent_service_journal(service_unit: str, limit: int):
    result = run_command(
        [
            "journalctl",
            "--user",
            "-u",
            service_unit,
            "-n",
            str(limit),
            "--no-pager",
            "--output=short-iso",
        ]
    )
    if not result["ok"]:
        return {
            "available": False,
            "lines": [],
            "error": result["stderr"].strip() or result["stdout"].strip() or f"journalctl exited with {result['returncode']}",
        }
    lines = [line.rstrip() for line in result["stdout"].splitlines() if line.strip()]
    return {
        "available": True,
        "lines": lines,
        "error": None,
    }


def extract_latest_guard_line(lines: list[str]):
    for line in reversed(lines):
        if "Guard:" in line:
            return line
    return None


def extract_latest_run_line(lines: list[str]):
    for line in reversed(lines):
        if "Runs: total=" in line:
            return line
    return None


def summarize_last_decision(path: Path):
    row = load_last_jsonl_row(path)
    if row is None:
        return {
            "available": False,
            "count": 0,
            "row": None,
        }
    return {
        "available": True,
        "count": count_jsonl_rows(path),
        "row": row,
    }


def summarize_last_trade(path: Path):
    row = load_last_jsonl_row(path)
    if row is None:
        return {
            "available": False,
            "count": 0,
            "row": None,
        }
    return {
        "available": True,
        "count": count_jsonl_rows(path),
        "row": row,
    }


def build_market_watch_status(
    config_file: Path,
    decision_log: Path,
    paper_trades_log: Path,
    timer_unit: str,
    service_unit: str,
    journal_lines: int,
):
    config = market_watch.load_runtime_config(config_file)
    timer = read_unit_show(timer_unit)
    service = read_unit_show(service_unit)
    journal = read_recent_service_journal(service_unit, journal_lines)
    return {
        "config": {
            "pairs": config["pairs"],
            "execution_timeframe": config["execution_timeframe"],
            "execution_mode": config["execution_mode"],
        },
        "timer": timer,
        "service": service,
        "journal": {
            **journal,
            "latest_guard_line": extract_latest_guard_line(journal["lines"]),
            "latest_run_line": extract_latest_run_line(journal["lines"]),
        },
        "last_decision": summarize_last_decision(decision_log),
        "last_trade": summarize_last_trade(paper_trades_log),
        "paths": {
            "config_file": str(config_file),
            "decision_log": str(decision_log),
            "paper_trades_log": str(paper_trades_log),
        },
    }


def emit_text(status: dict):
    lines = [
        "=" * 100,
        "SET AND FORGET MARKET WATCH STATUS",
        (
            f"Pairs: {','.join(status['config']['pairs'])} "
            f"| timeframe={status['config']['execution_timeframe']} "
            f"| mode={status['config']['execution_mode']}"
        ),
    ]

    timer = status["timer"]
    if timer.get("available"):
        lines.append(
            f"Timer: active={timer.get('ActiveState')} sub={timer.get('SubState')} "
            f"| next={timer.get('NextElapseUSecRealtime') or 'n/a'} "
            f"| last={timer.get('LastTriggerUSec') or 'n/a'}"
        )
    else:
        lines.append(f"Timer: unavailable | {timer.get('error')}")

    service = status["service"]
    if service.get("available"):
        lines.append(
            f"Service: active={service.get('ActiveState')} sub={service.get('SubState')} "
            f"| result={service.get('Result') or 'n/a'}"
        )
    else:
        lines.append(f"Service: unavailable | {service.get('error')}")

    journal = status["journal"]
    if journal.get("available"):
        lines.append(f"Last run log: {journal.get('latest_run_line') or 'n/a'}")
        lines.append(f"Last guard log: {journal.get('latest_guard_line') or 'n/a'}")
    else:
        lines.append(f"Journal: unavailable | {journal.get('error')}")

    last_decision = status["last_decision"]
    if last_decision["available"]:
        row = last_decision["row"]
        lines.append(
            f"Last decision: {row.get('timestamp')} | pair={row.get('pair')} "
            f"| decision={row.get('decision')} | paper_trade_created={row.get('paper_trade_created')} "
            f"| log_rows={last_decision['count']}"
        )
    else:
        lines.append("Last decision: none")

    last_trade = status["last_trade"]
    if last_trade["available"]:
        row = last_trade["row"]
        lines.append(
            f"Last trade: {row.get('timestamp')} | pair={row.get('pair')} "
            f"| decision={row.get('decision')} | confidence={row.get('confidence_score')} "
            f"| trade_rows={last_trade['count']}"
        )
    else:
        lines.append("Last trade: none")

    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Show the current Set & Forget market watch ops status.")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--config-file", type=Path, default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--decision-log", type=Path, default=automation.AUTOMATION_DECISIONS_LOG_FILE)
    parser.add_argument("--paper-trades-log", type=Path, default=engine.PAPER_TRADES_LOG_FILE)
    parser.add_argument("--timer-unit", default=DEFAULT_TIMER_UNIT)
    parser.add_argument("--service-unit", default=DEFAULT_SERVICE_UNIT)
    parser.add_argument("--journal-lines", type=int, default=20)
    args = parser.parse_args()

    status = build_market_watch_status(
        config_file=args.config_file,
        decision_log=args.decision_log,
        paper_trades_log=args.paper_trades_log,
        timer_unit=args.timer_unit,
        service_unit=args.service_unit,
        journal_lines=args.journal_lines,
    )

    if args.format == "json":
        json.dump(status, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return 0

    emit_text(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
