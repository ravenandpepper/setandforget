import argparse
import json
import sys
import webbrowser
from pathlib import Path

import ctrader_oauth
import pepperstone_config


BASE_DIR = Path(__file__).resolve().parent


def emit_output(result: dict, output_format: str):
    if output_format == "text":
        lines = [
            "=" * 100,
            "CTRADER OAUTH",
            f"Status: {result['status']}",
        ]
        if result.get("authorization_url"):
            lines.append(f"Authorization URL: {result['authorization_url']}")
        if result.get("env_file"):
            lines.append(f"Env file: {result['env_file']}")
        if result.get("token_summary"):
            summary = result["token_summary"]
            lines.append(f"Token type: {summary.get('token_type')}")
            lines.append(f"Access token expires at: {summary.get('access_token_expires_at')}")
        if result.get("errors"):
            lines.append(f"Errors: {' | '.join(result['errors'])}")
        print("\n".join(lines))
        return

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()


def run_authorize(env_file: Path, open_browser: bool):
    config = ctrader_oauth.load_oauth_config(BASE_DIR)
    auth_url = ctrader_oauth.build_authorization_url(config)
    if open_browser:
        webbrowser.open(auth_url)
    code = ctrader_oauth.wait_for_authorization_code(config["redirect_uri"])
    tokens = ctrader_oauth.exchange_authorization_code(config, code)
    ctrader_oauth.upsert_env_file(env_file, ctrader_oauth.build_env_updates(tokens))
    return {
        "status": "authorized",
        "authorization_url": auth_url,
        "env_file": str(env_file),
        "token_summary": {
            "token_type": tokens.get("token_type"),
            "access_token_expires_at": tokens.get("access_token_expires_at"),
        },
    }


def run_exchange_code(env_file: Path, code: str):
    config = ctrader_oauth.load_oauth_config(BASE_DIR)
    tokens = ctrader_oauth.exchange_authorization_code(config, code)
    ctrader_oauth.upsert_env_file(env_file, ctrader_oauth.build_env_updates(tokens))
    return {
        "status": "authorized",
        "env_file": str(env_file),
        "token_summary": {
            "token_type": tokens.get("token_type"),
            "access_token_expires_at": tokens.get("access_token_expires_at"),
        },
    }


def run_refresh(env_file: Path):
    config = ctrader_oauth.load_oauth_config(BASE_DIR)
    loaded_env = pepperstone_config.load_config(BASE_DIR)
    refresh_token = loaded_env.get("refresh_token")
    if not refresh_token:
        raise ValueError("refresh_token_missing")
    tokens = ctrader_oauth.refresh_access_token(config, refresh_token)
    ctrader_oauth.upsert_env_file(env_file, ctrader_oauth.build_env_updates(tokens))
    return {
        "status": "refreshed",
        "env_file": str(env_file),
        "token_summary": {
            "token_type": tokens.get("token_type"),
            "access_token_expires_at": tokens.get("access_token_expires_at"),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Authorize a cTrader Open API app and persist OAuth tokens.")
    parser.add_argument("--action", choices=["authorize", "exchange-code", "refresh", "print-url"], default="print-url")
    parser.add_argument("--env-file", type=Path, default=ctrader_oauth.DEFAULT_ENV_FILE)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--code")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()

    try:
        if args.action == "print-url":
            config = ctrader_oauth.load_oauth_config(BASE_DIR)
            result = {
                "status": "ready",
                "authorization_url": ctrader_oauth.build_authorization_url(config),
                "env_file": str(args.env_file),
            }
        elif args.action == "authorize":
            result = run_authorize(args.env_file, args.open_browser)
        elif args.action == "exchange-code":
            if not args.code:
                raise ValueError("authorization_code_required")
            result = run_exchange_code(args.env_file, args.code)
        else:
            result = run_refresh(args.env_file)
        emit_output(result, args.format)
        return 0
    except Exception as error:
        emit_output(
            {
                "status": "error",
                "errors": [str(error)],
                "env_file": str(args.env_file),
            },
            args.format,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
