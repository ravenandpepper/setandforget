import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone

import market_data_fetch
import market_data_ingest


DEFAULT_MAX_REQUESTS_PER_MINUTE = 6
DEFAULT_EXECUTION_TIMEFRAME = "4H"
DEFAULT_EXECUTION_MODE = "paper"
DEFAULT_MINUTE_SPACING = 1


def load_ingest_schema():
    return market_data_fetch.load_json(market_data_ingest.INGEST_SCHEMA_FILE)


def normalize_pairs(pairs: list[str]):
    normalized = []
    seen = set()
    for pair in pairs:
        value = market_data_ingest.normalize_pair(pair)
        if not value:
            raise ValueError("Every scheduled pair must be non-empty.")
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)

    if not normalized:
        raise ValueError("At least one pair is required to build a fetch schedule.")
    return normalized


def normalize_execution_timeframe(value: str):
    ingest_schema = load_ingest_schema()
    normalized = market_data_ingest.normalize_timeframe(value, ingest_schema)
    if not normalized:
        raise ValueError("Execution timeframe is required for the fetch schedule.")
    return normalized


def parse_schedule_timestamp(value: str | None):
    if value is None:
        return datetime.now(timezone.utc).replace(second=0, microsecond=0)
    return market_data_fetch.parse_iso_timestamp(value).replace(second=0, microsecond=0)


def serialize_schedule_timestamp(value: datetime):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_trigger_request(
    pair: str,
    scheduled_for: datetime,
    execution_timeframe: str,
    execution_mode: str,
    fxalex_confluence_enabled: bool,
    news_context_enabled: bool,
):
    return {
        "pair": pair,
        "execution_timeframe": execution_timeframe,
        "execution_mode": execution_mode,
        "trigger_time": serialize_schedule_timestamp(scheduled_for),
        "fxalex_confluence_enabled": fxalex_confluence_enabled,
        "news_context_enabled": news_context_enabled,
    }


def build_fetch_schedule(
    pairs: list[str],
    trigger_time: str | None,
    execution_timeframe: str = DEFAULT_EXECUTION_TIMEFRAME,
    execution_mode: str = DEFAULT_EXECUTION_MODE,
    max_requests_per_minute: int = DEFAULT_MAX_REQUESTS_PER_MINUTE,
    minute_spacing: int = DEFAULT_MINUTE_SPACING,
    fxalex_confluence_enabled: bool = False,
    news_context_enabled: bool = False,
):
    normalized_pairs = normalize_pairs(pairs)
    normalized_timeframe = normalize_execution_timeframe(execution_timeframe)
    requests_per_pair = len(market_data_fetch.TWELVEDATA_TIMEFRAMES)

    if max_requests_per_minute < 1:
        raise ValueError("max_requests_per_minute must be at least 1.")
    if minute_spacing < 1:
        raise ValueError("minute_spacing must be at least 1.")
    if max_requests_per_minute < requests_per_pair:
        raise ValueError(
            "max_requests_per_minute is lower than the per-pair candle cost. "
            f"Need at least {requests_per_pair} requests per minute."
        )

    pairs_per_minute = max_requests_per_minute // requests_per_pair
    if pairs_per_minute < 1:
        raise ValueError("The current request budget cannot schedule even one pair per minute.")

    base_trigger_time = parse_schedule_timestamp(trigger_time)
    buckets = []
    for bucket_index in range(math.ceil(len(normalized_pairs) / pairs_per_minute)):
        start = bucket_index * pairs_per_minute
        end = start + pairs_per_minute
        bucket_pairs = normalized_pairs[start:end]
        scheduled_for = base_trigger_time + timedelta(minutes=bucket_index * minute_spacing)
        buckets.append(
            {
                "bucket_index": bucket_index + 1,
                "scheduled_for": serialize_schedule_timestamp(scheduled_for),
                "pair_count": len(bucket_pairs),
                "pairs": bucket_pairs,
                "estimated_requests": len(bucket_pairs) * requests_per_pair,
                "trigger_requests": [
                    build_trigger_request(
                        pair=pair,
                        scheduled_for=scheduled_for,
                        execution_timeframe=normalized_timeframe,
                        execution_mode=execution_mode,
                        fxalex_confluence_enabled=fxalex_confluence_enabled,
                        news_context_enabled=news_context_enabled,
                    )
                    for pair in bucket_pairs
                ],
            }
        )

    effective_requests_per_minute = pairs_per_minute * requests_per_pair
    return {
        "provider": "twelvedata",
        "adapter": market_data_fetch.TWELVEDATA_ADAPTER_KEY,
        "execution_timeframe": normalized_timeframe,
        "execution_mode": execution_mode,
        "request_budget": {
            "max_requests_per_minute": max_requests_per_minute,
            "requests_per_pair": requests_per_pair,
            "pairs_per_minute": pairs_per_minute,
            "effective_requests_per_minute": effective_requests_per_minute,
            "unused_requests_per_minute": max_requests_per_minute - effective_requests_per_minute,
            "pair_atomic_scheduling": True,
        },
        "schedule": {
            "base_trigger_time": serialize_schedule_timestamp(base_trigger_time),
            "minute_spacing": minute_spacing,
            "total_pairs": len(normalized_pairs),
            "total_estimated_requests": len(normalized_pairs) * requests_per_pair,
            "estimated_completion_minutes": len(buckets),
            "buckets": buckets,
        },
    }


def emit_output(plan: dict, output_format: str):
    if output_format == "json":
        json.dump(plan, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return

    budget = plan["request_budget"]
    schedule = plan["schedule"]
    lines = [
        "=" * 100,
        "MARKET DATA FETCH SCHEDULE",
        f"Provider: {plan['provider']} | adapter={plan['adapter']}",
        (
            f"Timeframe: {plan['execution_timeframe']} | mode={plan['execution_mode']} "
            f"| total_pairs={schedule['total_pairs']}"
        ),
        (
            f"Budget: max={budget['max_requests_per_minute']}/min "
            f"requests_per_pair={budget['requests_per_pair']} "
            f"pairs_per_minute={budget['pairs_per_minute']} "
            f"effective={budget['effective_requests_per_minute']}/min "
            f"unused={budget['unused_requests_per_minute']}/min"
        ),
        (
            f"Base trigger: {schedule['base_trigger_time']} | buckets={len(schedule['buckets'])} "
            f"| estimated_completion_minutes={schedule['estimated_completion_minutes']}"
        ),
    ]
    for bucket in schedule["buckets"]:
        lines.append(
            f"- {bucket['scheduled_for']}: pairs={','.join(bucket['pairs'])} "
            f"estimated_requests={bucket['estimated_requests']}"
        )
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Build a minute-bucketed fetch schedule for Twelve Data trigger-only runs.")
    parser.add_argument("--pairs", required=True, help="Comma-separated list of forex pairs, for example EURUSD,GBPUSD,USDJPY")
    parser.add_argument("--trigger-time", default=None, help="Base UTC trigger time in ISO-8601 form. Defaults to the current UTC minute.")
    parser.add_argument("--execution-timeframe", default=DEFAULT_EXECUTION_TIMEFRAME)
    parser.add_argument("--execution-mode", default=DEFAULT_EXECUTION_MODE)
    parser.add_argument("--max-requests-per-minute", type=int, default=DEFAULT_MAX_REQUESTS_PER_MINUTE)
    parser.add_argument("--minute-spacing", type=int, default=DEFAULT_MINUTE_SPACING)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    plan = build_fetch_schedule(
        pairs=[item.strip() for item in args.pairs.split(",") if item.strip()],
        trigger_time=args.trigger_time,
        execution_timeframe=args.execution_timeframe,
        execution_mode=args.execution_mode,
        max_requests_per_minute=args.max_requests_per_minute,
        minute_spacing=args.minute_spacing,
    )
    emit_output(plan, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
