import os
from pathlib import Path

import runtime_env
from pepperstone_models import PepperstoneConfig, PepperstoneRuntimeConfig


PEPPERSTONE_REQUIRED_ENV_VARS = [
    "PEPPERSTONE_ENVIRONMENT",
    "PEPPERSTONE_ACCOUNT_ID",
    "PEPPERSTONE_API_KEY",
    "PEPPERSTONE_API_SECRET",
]
PEPPERSTONE_OPTIONAL_ENV_VARS = [
    "PEPPERSTONE_API_BASE_URL",
]


def describe_runtime_config(base_dir: Path) -> PepperstoneRuntimeConfig:
    runtime_env.load_standardized_env(base_dir)
    env_summary = runtime_env.summarize_env_keys(
        required_keys=PEPPERSTONE_REQUIRED_ENV_VARS,
        optional_keys=PEPPERSTONE_OPTIONAL_ENV_VARS,
    )
    return {
        "adapter_key": "pepperstone",
        "env_namespace": "PEPPERSTONE_*",
        **env_summary,
    }


def load_config(base_dir: Path) -> PepperstoneConfig:
    runtime_summary = describe_runtime_config(base_dir)
    return {
        "environment": os.environ.get("PEPPERSTONE_ENVIRONMENT"),
        "account_id": os.environ.get("PEPPERSTONE_ACCOUNT_ID"),
        "api_key": os.environ.get("PEPPERSTONE_API_KEY"),
        "api_secret": os.environ.get("PEPPERSTONE_API_SECRET"),
        "api_base_url": os.environ.get("PEPPERSTONE_API_BASE_URL"),
        "configured": runtime_summary["configured"],
    }
