#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_SOURCE="$ROOT_DIR/deploy/systemd/setandforget-tradingview-webhook.service"
UNIT_TARGET="${HOME}/.config/systemd/user/setandforget-tradingview-webhook.service"

mkdir -p "${HOME}/.config/systemd/user"
cp "$UNIT_SOURCE" "$UNIT_TARGET"
systemctl --user daemon-reload
systemctl --user enable --now setandforget-tradingview-webhook.service
systemctl --user status setandforget-tradingview-webhook.service --no-pager
