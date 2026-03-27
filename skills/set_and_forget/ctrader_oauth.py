import json
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Event
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import urlopen

import pepperstone_config


DEFAULT_ENV_FILE = Path.home() / ".config" / "openclaw" / "gateway.env"
DEFAULT_AUTH_BASE_URL = "https://id.ctrader.com"
DEFAULT_TOKEN_BASE_URL = "https://openapi.ctrader.com"


def load_oauth_config(base_dir: Path):
    config = pepperstone_config.load_config(base_dir)
    return {
        "client_id": config.get("client_id"),
        "client_secret": config.get("client_secret"),
        "redirect_uri": config.get("redirect_uri"),
        "auth_base_url": config.get("auth_base_url") or DEFAULT_AUTH_BASE_URL,
        "token_base_url": config.get("api_base_url") or DEFAULT_TOKEN_BASE_URL,
    }


def validate_oauth_config(config: dict):
    missing = []
    for key in ["client_id", "client_secret", "redirect_uri"]:
        if not config.get(key):
            missing.append(key)
    if missing:
        raise ValueError(f"missing_oauth_config:{','.join(missing)}")


def build_authorization_url(config: dict, scope: str = "trading"):
    validate_oauth_config(config)
    params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "scope": scope,
        "product": "web",
    }
    query = urlencode(params, quote_via=quote)
    return f"{config['auth_base_url'].rstrip('/')}/my/settings/openapi/grantingaccess/?{query}"


def exchange_authorization_code(config: dict, code: str, opener=urlopen):
    validate_oauth_config(config)
    params = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config["redirect_uri"],
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
    }
    query = urlencode(params, quote_via=quote)
    url = f"{config['token_base_url'].rstrip('/')}/apps/token?{query}"
    with opener(url) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return normalize_token_payload(payload)


def refresh_access_token(config: dict, refresh_token: str, opener=urlopen):
    validate_oauth_config(config)
    params = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
    }
    query = urlencode(params, quote_via=quote)
    url = f"{config['token_base_url'].rstrip('/')}/apps/token?{query}"
    with opener(url) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return normalize_token_payload(payload)


def normalize_token_payload(payload: dict):
    access_token = payload.get("accessToken")
    refresh_token = payload.get("refreshToken")
    expires_in = payload.get("expiresIn")
    token_type = payload.get("tokenType")
    error_code = payload.get("errorCode")
    description = payload.get("description")

    if error_code:
        raise ValueError(f"oauth_error:{error_code}:{description or 'no_description'}")
    if not access_token or not refresh_token:
        raise ValueError("oauth_error:missing_tokens")

    expires_at = None
    if isinstance(expires_in, (int, float)):
        expires_at = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": token_type,
        "expires_in": expires_in,
        "access_token_expires_at": expires_at,
    }


def build_env_updates(tokens: dict):
    return {
        "CTRADER_ACCESS_TOKEN": tokens["access_token"],
        "CTRADER_REFRESH_TOKEN": tokens["refresh_token"],
        "CTRADER_TOKEN_TYPE": tokens.get("token_type") or "bearer",
        "CTRADER_ACCESS_TOKEN_EXPIRES_AT": tokens.get("access_token_expires_at") or "",
    }


def upsert_env_file(path: Path, updates: dict):
    existing_lines = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8").splitlines()

    remaining = dict(updates)
    written_lines = []
    for raw_line in existing_lines:
        line = raw_line.rstrip("\n")
        if "=" not in line or line.lstrip().startswith("#"):
            written_lines.append(line)
            continue
        key, _value = line.split("=", 1)
        if key in remaining:
            written_lines.append(f"{key}={remaining.pop(key)}")
        else:
            written_lines.append(line)

    for key, value in remaining.items():
        written_lines.append(f"{key}={value}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(written_lines) + "\n", encoding="utf-8")


def wait_for_authorization_code(redirect_uri: str, timeout_seconds: int = 300):
    parsed = urlparse(redirect_uri)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("redirect_uri_must_be_local_http")

    expected_path = parsed.path or "/"
    result = {
        "code": None,
        "error": None,
    }
    ready = Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            request_url = urlparse(self.path)
            if request_url.path != expected_path:
                self.send_response(404)
                self.end_headers()
                return

            query = parse_qs(request_url.query)
            result["code"] = query.get("code", [None])[0]
            result["error"] = query.get("error", [None])[0]

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>cTrader authorization received</h1><p>You can close this tab and return to the terminal.</p></body></html>"
            )
            ready.set()

        def log_message(self, _format, *_args):
            return

    server = HTTPServer((parsed.hostname, parsed.port or 80), CallbackHandler)
    server.timeout = timeout_seconds

    while not ready.is_set():
        server.handle_request()
        if not ready.is_set():
            timeout_seconds -= server.timeout
            if timeout_seconds <= 0:
                server.server_close()
                raise TimeoutError("authorization_timeout")

    server.server_close()
    if result["error"]:
        raise ValueError(f"authorization_error:{result['error']}")
    if not result["code"]:
        raise ValueError("authorization_code_missing")
    return result["code"]
