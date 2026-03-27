# AGENTS.md

## Project purpose
This project builds a Set & Forget trading engine for paper trading and later structured automation.

## Operating context
1. Read `RUN_STATE.md` first for the current operational state, tournament meaning, start conditions, and notification expectations.
2. Use `AGENTS.md` for stable project rules and `RUN_STATE.md` for current state.

## Core architecture
1. Primary strategy: Set & Forget Swing Strategy
2. Secondary advisory layer: fxalex
3. Hard gates from the primary strategy are always leading
4. Advisory layers may only adjust confidence or signal conflict

## Strategy priority
1. Set & Forget is the source of truth
2. fxalex is advisory only
3. fxalex may never override a WAIT or NO-GO from the primary engine

## Development rules
1. Work incrementally
2. Make one improvement per iteration
3. Prefer small, testable changes
4. Do not broaden scope unless explicitly asked
5. Keep decision outputs explainable

## Decision output requirements
Every decision flow should aim to return:
1. decision
2. confidence_score
3. reason_codes
4. summary

## Safety boundaries
1. Paper trading before live trading
2. No broker integration unless explicitly requested
3. No live execution unless explicitly requested
4. Do not modify credentials or infrastructure without permission

## Project paths
1. skills/set_and_forget/
2. skills/fxalex/
3. /Users/jeroenderaaf/alexbecker_dump/fxalexg/processed/

## Validation expectations
After changes:
1. Validate JSON files if modified
2. Validate Python syntax if modified
3. Run the smallest relevant local test possible
