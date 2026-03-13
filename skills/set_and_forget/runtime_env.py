import os
from pathlib import Path


def env_file_candidates(base_dir: Path):
    resolved_base_dir = base_dir.resolve()
    workspace_root = resolved_base_dir.parent.parent
    return [
        workspace_root / ".env",
        resolved_base_dir / ".env",
        Path.home() / ".config" / "openclaw" / "gateway.env",
    ]


def env_source_order(base_dir: Path):
    return [
        "process_environment",
        *[str(path.expanduser()) for path in env_file_candidates(base_dir)],
    ]


def parse_env_line(raw_line: str):
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None

    if line.startswith("export "):
        line = line[len("export "):].lstrip()

    if "=" not in line:
        return None

    key, value = line.split("=", 1)
    key = key.strip()
    if not key:
        return None

    return key, value.strip().strip('"').strip("'")


def load_standardized_env(base_dir: Path):
    checked_files = []
    loaded_files = []
    seen = set()

    for candidate in env_file_candidates(base_dir):
        candidate = candidate.expanduser()
        if candidate in seen:
            continue
        seen.add(candidate)
        checked_files.append(str(candidate))

        if not candidate.exists():
            continue

        loaded_files.append(str(candidate))
        with open(candidate, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                parsed = parse_env_line(raw_line)
                if parsed is None:
                    continue
                key, value = parsed
                os.environ.setdefault(key, value)

    return {
        "source_order": env_source_order(base_dir),
        "files_checked": checked_files,
        "files_loaded": loaded_files,
        "override_policy": "process_env_first_then_setdefault_from_files",
    }


def summarize_env_keys(required_keys: list[str], optional_keys: list[str] | None = None):
    optional_keys = optional_keys or []

    present_required = [key for key in required_keys if os.environ.get(key)]
    missing_required = [key for key in required_keys if not os.environ.get(key)]
    present_optional = [key for key in optional_keys if os.environ.get(key)]

    return {
        "required_env_vars": required_keys,
        "optional_env_vars": optional_keys,
        "present_required_env_vars": present_required,
        "present_optional_env_vars": present_optional,
        "missing_required_env_vars": missing_required,
        "configured": not missing_required,
    }
