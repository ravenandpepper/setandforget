import os
from pathlib import Path

import runtime_env
from pepperstone_models import PepperstoneConfig, PepperstoneRuntimeConfig


PEPPERSTONE_REQUIRED_ENV_VARS = [
    "CTRADER_ENVIRONMENT",
    "CTRADER_ACCOUNT_ID",
    "CTRADER_CLIENT_ID",
    "CTRADER_CLIENT_SECRET",
    "CTRADER_REDIRECT_URI",
]
PEPPERSTONE_OPTIONAL_ENV_VARS = [
    "CTRADER_AUTH_BASE_URL",
    "CTRADER_API_BASE_URL",
    "CTRADER_ACCESS_TOKEN",
    "CTRADER_REFRESH_TOKEN",
    "CTRADER_TOKEN_TYPE",
    "CTRADER_ACCESS_TOKEN_EXPIRES_AT",
]


def describe_runtime_config(base_dir: Path) -> PepperstoneRuntimeConfig:
    runtime_env.load_standardized_env(base_dir)
    env_summary = runtime_env.summarize_env_keys(
        required_keys=PEPPERSTONE_REQUIRED_ENV_VARS,
        optional_keys=PEPPERSTONE_OPTIONAL_ENV_VARS,
    )
    return {
        "adapter_key": "pepperstone",
        "env_namespace": "CTRADER_*",
        **env_summary,
    }


def load_config(base_dir: Path) -> PepperstoneConfig:
    runtime_summary = describe_runtime_config(base_dir)
    return {
        "environment": os.environ.get("CTRADER_ENVIRONMENT"),
        "account_id": os.environ.get("CTRADER_ACCOUNT_ID"),
        "client_id": os.environ.get("CTRADER_CLIENT_ID"),
        "client_secret": os.environ.get("CTRADER_CLIENT_SECRET"),
        "redirect_uri": os.environ.get("CTRADER_REDIRECT_URI"),
        "auth_base_url": os.environ.get("CTRADER_AUTH_BASE_URL"),
        "api_base_url": os.environ.get("CTRADER_API_BASE_URL"),
        "access_token": os.environ.get("CTRADER_ACCESS_TOKEN"),
        "refresh_token": os.environ.get("CTRADER_REFRESH_TOKEN"),
        "token_type": os.environ.get("CTRADER_TOKEN_TYPE"),
        "access_token_expires_at": os.environ.get("CTRADER_ACCESS_TOKEN_EXPIRES_AT"),
        "configured": runtime_summary["configured"],
    }
