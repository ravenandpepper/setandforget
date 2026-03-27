# OpenClaw Access

## Browser access
- Preferred path: private Tailscale access on the VPS.
- Hostname: `setandforget-vps.tailf8ffa3.ts.net`
- Get a fresh tokenized dashboard URL from the VPS:
  - `ssh traderops@38.242.214.188 "openclaw dashboard --no-open"`

## Current setup
- OpenClaw gateway runs on the VPS as the user service `openclaw-gateway.service`.
- Tailscale Serve proxies `https://setandforget-vps.tailf8ffa3.ts.net/` to local gateway port `127.0.0.1:18789`.
- The gateway allows the Tailscale Control UI origin via `gateway.controlUi.allowedOrigins`.

## If the browser blocks access
- `origin not allowed`
  - Re-check `gateway.controlUi.allowedOrigins` in `/home/traderops/.openclaw/openclaw.json`.
  - Restart the gateway: `ssh traderops@38.242.214.188 "systemctl --user restart openclaw-gateway.service"`
- `pairing required`
  - Approve the pending browser device:
    - `ssh traderops@38.242.214.188 "openclaw devices approve --latest"`

## Notes
- The Tailscale and OpenClaw runtime config on the VPS is operational state, not repo state.
- Do not commit dashboard tokens or browser-specific device ids into the repository.
