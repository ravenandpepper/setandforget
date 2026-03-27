# RUN_STATE

## Current focus
- Project: Set & Forget with an OpenClaw multi-model tournament layer.
- Goal: run the tournament in paper mode first, compare the baseline against multiple models, and keep outputs explainable.
- Current broker status: no automatic broker execution yet. cTrader/Pepperstone auto-execution is a later step and may be blocked by third-party approval.

## What "the tournament" means
- "The tournament" in this workspace means the OpenClaw multi-model comparison flow described in `skills/set_and_forget/OPENCLAW_TOURNAMENT.md`.
- The same objective `feature_snapshot` is sent to multiple models.
- Set & Forget remains the baseline and source of truth.
- Hard gates from the primary strategy are non-overrideable.
- fxalex is advisory only and may not override a `WAIT` or `NO-GO`.
- The tournament is for paper performance and shadow-portfolio comparison, not direct live trading.

## Current tournament participants
- `openrouter/anthropic/claude-opus-4.6`
- `openrouter/anthropic/claude-sonnet-4.6`
- `openrouter/minimax/minimax-m1`
- `openrouter/moonshotai/kimi-k2`

## Current operational assumptions
- Market scope for the tournament: traditional FX/forex market flow used by Set & Forget, not crypto.
- Timeframe focus: the current strategy flow uses `4H` execution context.
- Execution mode: paper only.
- Current scheduled market-watch pairs: `EURJPY`, `EURGBP`.
- Dashboard/demo nuance: if the dashboard is showing fallback data, that is demo data and not a real paper trade.

## Live runtime status source
- For live status questions, prefer a real runtime artifact over static documentation.
- In the OpenClaw workspace mirror, prefer `skills/set_and_forget/openclaw_runtime_status.json` under the active project mirror.
- In the current VPS deployment, the mirrored workspace path is `/home/traderops/.openclaw/workspace/setandforget/skills/set_and_forget/openclaw_runtime_status.json`.
- The source-of-truth runtime checkout still writes `/home/traderops/setandforget/skills/set_and_forget/openclaw_runtime_status.json`, and the mirror should be synced from that file.
- The live tournament sidecar config is `skills/set_and_forget/live_tournament_sidecar.json`.
- The tournament sidecar should stay disabled by default until explicitly enabled.
- Use `RUN_STATE.md` for meaning and policy, and the runtime status artifact for whether the market-watch flow or tournament most recently ran.

## Start condition
- The tournament should be considered ready to begin when traditional FX markets are open and the user wants the run to start.
- "Ready to begin" is not the same as "already started".
- If the user asks for a notification when markets open and the tournament can begin, interpret that as the Set & Forget/OpenClaw paper tournament in this repo unless the user explicitly says otherwise.

## Status interpretation
- If traditional FX markets are open, say that the tournament can begin now.
- Only say that the tournament has already started if there is an explicit run signal such as a confirmed user start, a run log, a status file, or an active process that proves it.
- If there is no explicit started signal, do not answer only "it has not started"; state both whether the market is open and whether the tournament is ready to start now.
- For weekday daytime questions in Europe/Amsterdam, do not treat the absence of a started flag as proof that the tournament cannot begin.

## Notification expectation
- If asked to notify when the tournament can begin, assume the user wants a concise message that markets are open and the tournament can start.
- If asked "is it started?" during open FX hours and there is no explicit started signal, answer: markets are open and the tournament is ready to start, but it is not confirmed as already running.
- If there is ambiguity, first check this file and relevant project files before asking the user to restate what "the tournament" means.

## Response pattern for Lucy/OpenClaw
- For "Is the tournament started?": answer in two parts: `1. market-open/ready status` and `2. confirmed-running status`.
- Preferred wording when FX is open but no explicit run signal exists: `De forexmarkt is open. Het toernooi kan nu starten, maar het is niet bevestigd als al draaiend.`
- Preferred wording when FX is closed: `De forexmarkt is gesloten. Het toernooi is nu niet startklaar.`
- Preferred wording when FX is open and a run signal exists: `De forexmarkt is open en het toernooi draait al.`
- Do not collapse `ready to start` into `not started yet` without also stating whether the market is open right now.
- Keep the answer concise. Do not append a filesystem audit summary unless the user explicitly asks what you checked.
- If the user asks only for status, do not offer to start the tournament and do not offer to set a notification unless the user explicitly asks for one of those actions.
- Do not end a status answer with a follow-up question unless the user asked for an action.
- For live status questions, check the runtime status artifact first before inferring from the absence of logs in the OpenClaw workspace mirror.

## Orchestrator behavior
- Before asking clarifying questions about the meaning of "the tournament", first inspect:
  - `RUN_STATE.md`
  - `AGENTS.md`
  - `skills/set_and_forget/OPENCLAW_TOURNAMENT.md`
- Only ask the user for clarification if those files still leave ambiguity.

## Short orchestrator prompt
Use this as the short instruction for Lucy/OpenClaw:

`For this workspace, always read RUN_STATE.md and AGENTS.md before asking what "the tournament" means. In this project, "the tournament" refers to the OpenClaw multi-model Set & Forget paper tournament unless the user explicitly says otherwise. For live status, prefer the runtime status artifact over static docs. Distinguish clearly between ready to start and already started, answer status questions with both market-open status and confirmed-running status, and keep status-only replies concise with no unsolicited next-step offers.`
