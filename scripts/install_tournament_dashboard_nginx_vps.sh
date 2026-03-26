#!/usr/bin/env bash

set -euo pipefail

CONF_PATH="/etc/nginx/sites-available/setandforget-tradingview-webhook"
REPO_ROOT="/home/traderops/setandforget"
SNIPPET_FILE="$REPO_ROOT/deploy/nginx/setandforget-tournament-dashboard.locations.conf.example"
TMP_FILE="$(mktemp)"
BACKUP_SUFFIX="$(date +%Y%m%d%H%M%S)"

cleanup() {
  rm -f "$TMP_FILE"
}

trap cleanup EXIT

if [[ ! -f "$SNIPPET_FILE" ]]; then
  echo "Missing snippet file: $SNIPPET_FILE" >&2
  exit 1
fi

if [[ ! -f "$CONF_PATH" ]]; then
  echo "Missing nginx site config: $CONF_PATH" >&2
  exit 1
fi

sudo cp "$CONF_PATH" "${CONF_PATH}.bak.${BACKUP_SUFFIX}"
sudo cat "$CONF_PATH" > "$TMP_FILE"

python3 - "$TMP_FILE" "$SNIPPET_FILE" <<'PY'
import sys
from pathlib import Path
import re

conf_path = Path(sys.argv[1])
snippet_path = Path(sys.argv[2])
marker_begin = "# setandforget tournament dashboard begin"
marker_end = "# setandforget tournament dashboard end"

conf = conf_path.read_text(encoding="utf-8")
snippet = snippet_path.read_text(encoding="utf-8").rstrip()

pattern = re.compile(
    rf"\n?    {re.escape(marker_begin)}.*?    {re.escape(marker_end)}\n?",
    re.DOTALL,
)

if marker_begin in conf and marker_end in conf:
    updated = pattern.sub("\n" + snippet + "\n", conf, count=1)
    conf_path.write_text(updated, encoding="utf-8")
    print("Dashboard snippet replaced in nginx site config.")
    raise SystemExit(0)

anchor = "    client_max_body_size 64k;\n"
if anchor not in conf:
    raise SystemExit("Could not find nginx insertion anchor.")

updated = conf.replace(anchor, anchor + "\n" + snippet + "\n", 1)
conf_path.write_text(updated, encoding="utf-8")
print("Dashboard snippet inserted into nginx site config.")
PY

sudo cp "$TMP_FILE" "$CONF_PATH"
sudo nginx -t
sudo systemctl reload nginx

echo "Dashboard route installed."
echo "Open: http://38.242.214.188/tournament/"
