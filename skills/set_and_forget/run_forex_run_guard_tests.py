import forex_run_guard


def assert_allows_open_h4_close():
    result = forex_run_guard.evaluate_forex_run_guard(
        trigger_time="2026-03-26T12:00:00Z",
        execution_timeframe="4H",
        pairs=["GBPJPY", "EURJPY", "EURGBP"],
    )
    assert result["eligible"] is True, "Open weekday H4 close should pass the guard"
    assert result["market_status"] == "open", "Open weekday should report market open"


def assert_allows_european_morning_h4_close():
    result = forex_run_guard.evaluate_forex_run_guard(
        trigger_time="2026-03-27T08:00:00Z",
        execution_timeframe="4H",
        pairs=["GBPJPY", "EURJPY", "EURGBP"],
    )
    assert result["eligible"] is True, "European morning H4 close should now pass the guard"
    assert result["market_status"] == "open", "European morning session should still report market open"


def assert_blocks_weekend():
    result = forex_run_guard.evaluate_forex_run_guard(
        trigger_time="2026-03-28T12:00:00Z",
        execution_timeframe="4H",
        pairs=["GBPJPY", "EURJPY", "EURGBP"],
    )
    assert result["eligible"] is False, "Weekend trigger should be blocked"
    assert result["skip_reason_code"] == "FOREX_WEEKEND_CLOSED", "Weekend block should use the weekend reason code"


def assert_blocks_daily_break():
    result = forex_run_guard.evaluate_forex_run_guard(
        trigger_time="2026-03-26T20:59:00Z",
        execution_timeframe="4H",
        pairs=["GBPJPY", "EURJPY", "EURGBP"],
    )
    assert result["eligible"] is False, "Daily maintenance break should be blocked"
    assert result["skip_reason_code"] == "FOREX_DAILY_BREAK", "Daily break should use the break reason code"


def assert_blocks_off_cycle_h4():
    result = forex_run_guard.evaluate_forex_run_guard(
        trigger_time="2026-03-26T13:00:00Z",
        execution_timeframe="4H",
        pairs=["GBPJPY", "EURJPY", "EURGBP"],
    )
    assert result["eligible"] is False, "Non-H4-close timestamp should be blocked"
    assert result["skip_reason_code"] == "H4_NOT_CLOSED", "Off-cycle H4 trigger should use the H4 reason code"


def assert_blocks_outside_primary_session():
    result = forex_run_guard.evaluate_forex_run_guard(
        trigger_time="2026-03-26T20:00:00Z",
        execution_timeframe="4H",
        pairs=["GBPJPY", "EURJPY", "EURGBP"],
    )
    assert result["eligible"] is False, "Open market outside the primary session should still be blocked"
    assert result["skip_reason_code"] == "OUTSIDE_PRIMARY_SESSION", (
        "Open but off-session triggers should use the primary-session reason code"
    )


def main():
    assert_allows_open_h4_close()
    assert_allows_european_morning_h4_close()
    assert_blocks_weekend()
    assert_blocks_daily_break()
    assert_blocks_off_cycle_h4()
    assert_blocks_outside_primary_session()

    print("PASS 6/6 forex run guard scenarios")
    print("- forex_run_guard_allows_open_h4_close: eligible=True")
    print("- forex_run_guard_allows_european_morning_h4_close: london_session_allowed=True")
    print("- forex_run_guard_blocks_weekend_window: weekend_blocked=True")
    print("- forex_run_guard_blocks_daily_maintenance_break: break_blocked=True")
    print("- forex_run_guard_blocks_off_cycle_h4_trigger: h4_gate_ok=True")
    print("- forex_run_guard_blocks_outside_primary_session: primary_session_gate_ok=True")


if __name__ == "__main__":
    main()
