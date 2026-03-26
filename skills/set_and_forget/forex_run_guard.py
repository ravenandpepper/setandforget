from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import market_data_fetch


NEW_YORK = ZoneInfo("America/New_York")


def timestamp_now():
    return datetime.now(UTC).isoformat()


def parse_trigger_time(value: str | None):
    if value is None:
        return None
    parsed = market_data_fetch.parse_iso_timestamp(value)
    if parsed is None:
        return None
    return parsed.astimezone(UTC).replace(second=0, microsecond=0)


def serialize_timestamp(value: datetime | None):
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def is_weekend_closed(timestamp: datetime):
    new_york = timestamp.astimezone(NEW_YORK)
    minutes = new_york.hour * 60 + new_york.minute
    weekday = new_york.weekday()
    if weekday == 4 and minutes >= 17 * 60:
        return True
    if weekday == 5:
        return True
    if weekday == 6 and minutes < 17 * 60:
        return True
    return False


def is_daily_maintenance_break(timestamp: datetime):
    new_york = timestamp.astimezone(NEW_YORK)
    minutes = new_york.hour * 60 + new_york.minute
    return 16 * 60 + 59 <= minutes < 17 * 60 + 5


def is_h4_close_due(timestamp: datetime):
    return timestamp.minute == 0 and timestamp.hour % 4 == 0


def evaluate_forex_run_guard(trigger_time: str | None, execution_timeframe: str, pairs: list[str]):
    timestamp = parse_trigger_time(trigger_time)
    normalized_pairs = [pair.strip().upper() for pair in pairs if pair and pair.strip()]
    timeframe = (execution_timeframe or "").upper()

    if timestamp is None:
        return {
            "guard_version": "1.0",
            "evaluated_at": timestamp_now(),
            "eligible": False,
            "market_status": "unknown",
            "skip_reason_code": "TRIGGER_TIME_MISSING",
            "summary": "Er is geen bruikbare trigger_time om de forex-run guard te evalueren.",
            "trigger_time": trigger_time,
            "execution_timeframe": timeframe,
            "pairs": normalized_pairs,
        }

    if is_weekend_closed(timestamp):
        return {
            "guard_version": "1.0",
            "evaluated_at": timestamp_now(),
            "eligible": False,
            "market_status": "weekend_closed",
            "skip_reason_code": "FOREX_WEEKEND_CLOSED",
            "summary": "De forexmarkt is gesloten in het weekendvenster rond de New York close/open.",
            "trigger_time": serialize_timestamp(timestamp),
            "execution_timeframe": timeframe,
            "pairs": normalized_pairs,
        }

    if is_daily_maintenance_break(timestamp):
        return {
            "guard_version": "1.0",
            "evaluated_at": timestamp_now(),
            "eligible": False,
            "market_status": "daily_maintenance_break",
            "skip_reason_code": "FOREX_DAILY_BREAK",
            "summary": "De forexmarkt zit in de dagelijkse maintenance break rond 17:00 New York time.",
            "trigger_time": serialize_timestamp(timestamp),
            "execution_timeframe": timeframe,
            "pairs": normalized_pairs,
        }

    if timeframe == "4H" and not is_h4_close_due(timestamp):
        return {
            "guard_version": "1.0",
            "evaluated_at": timestamp_now(),
            "eligible": False,
            "market_status": "open_off_cycle",
            "skip_reason_code": "H4_NOT_CLOSED",
            "summary": "De markt is open, maar dit is geen H4 close-moment in UTC.",
            "trigger_time": serialize_timestamp(timestamp),
            "execution_timeframe": timeframe,
            "pairs": normalized_pairs,
        }

    if market_data_fetch.derive_session_window(serialize_timestamp(timestamp)) != "london_newyork_overlap":
        return {
            "guard_version": "1.0",
            "evaluated_at": timestamp_now(),
            "eligible": False,
            "market_status": "open_outside_primary_session",
            "skip_reason_code": "OUTSIDE_PRIMARY_SESSION",
            "summary": "De forexmarkt is open, maar het moment valt buiten de Set & Forget Londen-New York overlap.",
            "trigger_time": serialize_timestamp(timestamp),
            "execution_timeframe": timeframe,
            "pairs": normalized_pairs,
        }

    return {
        "guard_version": "1.0",
        "evaluated_at": timestamp_now(),
        "eligible": True,
        "market_status": "open",
        "skip_reason_code": None,
        "summary": "De forexmarkt is open en het trigger-moment is toegestaan voor deze batch-run.",
        "trigger_time": serialize_timestamp(timestamp),
        "execution_timeframe": timeframe,
        "pairs": normalized_pairs,
    }
