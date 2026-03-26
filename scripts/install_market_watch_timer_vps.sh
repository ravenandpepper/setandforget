#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_SOURCE="$ROOT_DIR/deploy/systemd/setandforget-market-watch.service"
TIMER_SOURCE="$ROOT_DIR/deploy/systemd/setandforget-market-watch.timer"
SERVICE_TARGET="${HOME}/.config/systemd/user/setandforget-market-watch.service"
TIMER_TARGET="${HOME}/.config/systemd/user/setandforget-market-watch.timer"

mkdir -p "${HOME}/.config/systemd/user"
cp "$SERVICE_SOURCE" "$SERVICE_TARGET"
cp "$TIMER_SOURCE" "$TIMER_TARGET"
systemctl --user daemon-reload
systemctl --user enable --now setandforget-market-watch.timer
systemctl --user status setandforget-market-watch.timer --no-pager
echo "---"
systemctl --user list-timers setandforget-market-watch.timer --no-pager
