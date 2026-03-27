#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_HOST="${REMOTE_HOST:-traderops@38.242.214.188}"
REMOTE_TOP_WORKSPACE_ROOT="${REMOTE_TOP_WORKSPACE_ROOT:-/home/traderops/.openclaw/workspace}"
REMOTE_WORKSPACE_ROOT="${REMOTE_WORKSPACE_ROOT:-/home/traderops/.openclaw/workspace/setandforget}"
REMOTE_ACTIVE_PROJECT_FILE="${REMOTE_ACTIVE_PROJECT_FILE:-/home/traderops/.openclaw/workspace/ACTIVE_PROJECT.md}"
REMOTE_TOP_RUN_STATE_FILE="${REMOTE_TOP_RUN_STATE_FILE:-/home/traderops/.openclaw/workspace/RUN_STATE.md}"
REMOTE_RUNTIME_STATUS_SOURCE="${REMOTE_RUNTIME_STATUS_SOURCE:-/home/traderops/setandforget/skills/set_and_forget/openclaw_runtime_status.json}"
REMOTE_RUNTIME_STATUS_MIRROR="${REMOTE_RUNTIME_STATUS_MIRROR:-/home/traderops/.openclaw/workspace/setandforget/skills/set_and_forget/openclaw_runtime_status.json}"

FILES=(
  "RUN_STATE.md"
  "AGENTS.md"
  "skills/set_and_forget/OPENCLAW_TOURNAMENT.md"
  "skills/set_and_forget/scheduled_market_watch.json"
  "skills/set_and_forget/live_tournament_sidecar.json"
)

for rel_path in "${FILES[@]}"; do
  if [[ ! -f "$REPO_ROOT/$rel_path" ]]; then
    echo "Missing local file: $REPO_ROOT/$rel_path" >&2
    exit 1
  fi
done

ssh "$REMOTE_HOST" "mkdir -p '$REMOTE_WORKSPACE_ROOT/skills/set_and_forget'"

for rel_path in "${FILES[@]}"; do
  src_path="$REPO_ROOT/$rel_path"
  dst_path="$REMOTE_WORKSPACE_ROOT/$rel_path"
  ssh "$REMOTE_HOST" "cat > '$dst_path'" < "$src_path"
  echo "Synced $rel_path -> $REMOTE_HOST:$dst_path"
done

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

cat > "$tmp_file" <<EOF
ACTIVE_PROJECT=$REMOTE_WORKSPACE_ROOT

For tournament meaning, market-focus, and policy questions, use:
- $REMOTE_WORKSPACE_ROOT/RUN_STATE.md
- $REMOTE_WORKSPACE_ROOT/AGENTS.md
- $REMOTE_WORKSPACE_ROOT/skills/set_and_forget/OPENCLAW_TOURNAMENT.md
- $REMOTE_WORKSPACE_ROOT/skills/set_and_forget/scheduled_market_watch.json
- $REMOTE_WORKSPACE_ROOT/skills/set_and_forget/live_tournament_sidecar.json

For live runtime status questions, check this file first:
- $REMOTE_RUNTIME_STATUS_MIRROR

Ignore /home/traderops/.openclaw/workspace/RUN_STATE.md for this project.
The current market focus is forex, not BTC/SOL crypto.
For questions about which markets/pairs are currently being watched, read $REMOTE_WORKSPACE_ROOT/skills/set_and_forget/scheduled_market_watch.json and answer with the exact configured symbols.
Do not ask the user to paste RUN_STATE.md, scheduled_market_watch.json, or other files that already exist in this workspace.
EOF

ssh "$REMOTE_HOST" "cat > '$REMOTE_ACTIVE_PROJECT_FILE'" < "$tmp_file"
echo "Synced ACTIVE_PROJECT.md -> $REMOTE_HOST:$REMOTE_ACTIVE_PROJECT_FILE"

cat > "$tmp_file" <<EOF
# RUN_STATE ROUTER

This top-level workspace RUN_STATE.md is not a project state file.
Do not answer project or tournament questions from this file.

ACTIVE_PROJECT=$REMOTE_WORKSPACE_ROOT

For the active Set & Forget project, use these files instead:
- $REMOTE_WORKSPACE_ROOT/RUN_STATE.md
- $REMOTE_WORKSPACE_ROOT/AGENTS.md
- $REMOTE_WORKSPACE_ROOT/skills/set_and_forget/OPENCLAW_TOURNAMENT.md
- $REMOTE_WORKSPACE_ROOT/skills/set_and_forget/scheduled_market_watch.json

For live runtime status, check this file first:
- $REMOTE_RUNTIME_STATUS_MIRROR

If any older AsterDEX content was previously present at $REMOTE_TOP_RUN_STATE_FILE, treat it as deprecated and ignore it.
For questions about watched markets/pairs, answer with the exact configured symbols from scheduled_market_watch.json.
Do not ask the user to paste files that already exist in the workspace.
EOF

ssh "$REMOTE_HOST" "cat > '$REMOTE_TOP_RUN_STATE_FILE'" < "$tmp_file"
echo "Synced top-level RUN_STATE router -> $REMOTE_HOST:$REMOTE_TOP_RUN_STATE_FILE"

ssh "$REMOTE_HOST" "if [ -f '$REMOTE_RUNTIME_STATUS_SOURCE' ]; then cp '$REMOTE_RUNTIME_STATUS_SOURCE' '$REMOTE_RUNTIME_STATUS_MIRROR'; echo 'Mirrored runtime status artifact.'; else echo 'Runtime status source missing; mirror not updated.'; fi"
echo "OpenClaw workspace mirror updated."
