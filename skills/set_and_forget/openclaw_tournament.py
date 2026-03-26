import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import feature_snapshot as feature_snapshot_module
import run_set_and_forget as engine
import runtime_env


BASE_DIR = Path(__file__).resolve().parent
FEATURE_SNAPSHOT_FILE = BASE_DIR / "feature_snapshot.example.json"
FEATURE_SNAPSHOT_SCHEMA_FILE = BASE_DIR / "feature_snapshot_schema.json"
DECISION_SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"
SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"
MODELS_FILE = BASE_DIR / "openclaw_tournament_models.example.json"
OUTPUT_SCHEMA_FILE = BASE_DIR / "openclaw_tournament_output_schema.json"
TOURNAMENT_RUNS_DIR = BASE_DIR / "openclaw_tournament_runs"
TOURNAMENT_LOG_FILE = BASE_DIR / "openclaw_tournament_log.jsonl"
ALLOWED_DECISIONS = {"BUY", "SELL", "WAIT", "NO-GO"}
DEFAULT_OPENCLAW_COMMAND = "openclaw"
DEFAULT_OPENCLAW_TIMEOUT_SECONDS = 180
DEFAULT_OPENCLAW_AGENT_PREFIX = "setandforget_tournament"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def timestamp_now():
    return datetime.now(UTC).isoformat()


def append_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def validate_models_manifest(manifest: dict):
    errors = []
    models = manifest.get("models")
    if not isinstance(models, list) or not models:
        return ["models manifest must contain a non-empty models list."]

    seen = set()
    for index, item in enumerate(models):
        prefix = f"models[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object.")
            continue
        model_id = item.get("model_id")
        adapter = item.get("adapter")
        if not isinstance(model_id, str) or not model_id.strip():
            errors.append(f"{prefix}.model_id must be a non-empty string.")
        if not isinstance(adapter, str) or not adapter.strip():
            errors.append(f"{prefix}.adapter must be a non-empty string.")
        if isinstance(model_id, str):
            if model_id in seen:
                errors.append(f"{prefix}.model_id must be unique.")
            seen.add(model_id)

    return errors


def validate_tournament_entry(entry: dict, schema: dict):
    errors = []
    for field in schema["fields"]:
        name = field["name"]
        if field.get("required") and name not in entry:
            errors.append(f"Missing required field: {name}")
            continue

        if name not in entry:
            continue

        value = entry[name]
        expected_type = field["type"]
        if expected_type == "string" and not isinstance(value, str):
            errors.append(f"Field {name} must be a string.")
            continue
        if expected_type == "boolean" and not isinstance(value, bool):
            errors.append(f"Field {name} must be a boolean.")
            continue
        if expected_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            errors.append(f"Field {name} must be an integer.")
            continue
        if expected_type == "array" and not isinstance(value, list):
            errors.append(f"Field {name} must be an array.")
            continue

        allowed_values = field.get("allowed_values")
        if allowed_values and value not in allowed_values:
            errors.append(f"Field {name} has invalid value {value!r}.")

        field_range = field.get("range")
        if field_range and isinstance(value, int) and not isinstance(value, bool):
            lower, upper = field_range
            if value < lower or value > upper:
                errors.append(f"Field {name} must be between {lower} and {upper}.")

    reason_codes = entry.get("reason_codes")
    if isinstance(reason_codes, list):
        if not reason_codes:
            errors.append("Field reason_codes must not be empty.")
        for index, code in enumerate(reason_codes):
            if not isinstance(code, str) or not code.strip():
                errors.append(f"Field reason_codes[{index}] must be a non-empty string.")

    return errors


def build_primary_payload(feature_snapshot: dict, skill: dict, decision_schema: dict):
    projected_snapshot = feature_snapshot_module.project_to_decision_snapshot(feature_snapshot)
    validation_errors = engine.validate_snapshot(projected_snapshot, decision_schema)
    if validation_errors:
        payload = engine.build_error_payload(
            snapshot=projected_snapshot,
            error_code="INPUT_SCHEMA_INVALID",
            summary="Projected snapshot validation failed before tournament evaluation.",
            errors=validation_errors,
        )
        return payload, 1

    result = engine.evaluate_rules(projected_snapshot, skill)
    result = engine.maybe_apply_fxalex_confluence(projected_snapshot, result, skill)
    result = engine.maybe_apply_news_context(projected_snapshot, result, skill)
    unknown_reason_codes = engine.validate_reason_codes(result["reason_codes"], decision_schema)
    if unknown_reason_codes:
        payload = engine.build_error_payload(
            snapshot=projected_snapshot,
            error_code="OUTPUT_SCHEMA_INVALID",
            summary="Primary tournament baseline contains invalid reason codes.",
            errors=[f"Unknown reason code: {code}" for code in unknown_reason_codes],
        )
        return payload, 1

    return engine.build_payload(projected_snapshot, result), 0


def slugify(value: str):
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return normalized or "model"


def get_openclaw_command():
    return shlex.split(os.environ.get("OPENCLAW_COMMAND", DEFAULT_OPENCLAW_COMMAND))


def get_openclaw_timeout_seconds():
    raw_timeout = os.environ.get("OPENCLAW_TOURNAMENT_TIMEOUT_SECONDS", str(DEFAULT_OPENCLAW_TIMEOUT_SECONDS))
    try:
        return max(1, int(raw_timeout))
    except ValueError:
        return DEFAULT_OPENCLAW_TIMEOUT_SECONDS


def build_openclaw_error_output(summary: str):
    return {
        "decision": "WAIT",
        "confidence_score": 0,
        "reason_codes": ["OUTPUT_SCHEMA_INVALID"],
        "summary": summary,
    }


def build_openclaw_agent_id(model: dict):
    explicit_agent_id = model.get("agent_id")
    if isinstance(explicit_agent_id, str) and explicit_agent_id.strip():
        return explicit_agent_id.strip()
    prefix = os.environ.get("OPENCLAW_TOURNAMENT_AGENT_PREFIX", DEFAULT_OPENCLAW_AGENT_PREFIX)
    return f"{prefix}_{slugify(model['model_id'])}"


def build_openclaw_workspace(model: dict, agent_id: str):
    explicit_workspace = model.get("workspace")
    if isinstance(explicit_workspace, str) and explicit_workspace.strip():
        return explicit_workspace.strip()
    return str(Path.home() / ".openclaw" / f"workspace-{agent_id}")


def run_openclaw_command(arguments: list[str]):
    command = [*get_openclaw_command(), *arguments]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=BASE_DIR,
        check=False,
    )


def read_configured_openclaw_agents():
    result = run_openclaw_command(["config", "get", "agents.list", "--json"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "openclaw config get failed")

    try:
        agents = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"openclaw config get returned invalid JSON: {exc}") from exc

    if not isinstance(agents, list):
        raise RuntimeError("openclaw agents.list must be a JSON array")
    return agents


def ensure_openclaw_agent(model: dict):
    agent_id = build_openclaw_agent_id(model)
    workspace = build_openclaw_workspace(model, agent_id)
    configured_agents = read_configured_openclaw_agents()
    existing = next((item for item in configured_agents if item.get("id") == agent_id), None)

    if existing is not None:
        existing_model = existing.get("model")
        if existing_model not in {None, model["model_id"]}:
            raise RuntimeError(
                f'openclaw agent "{agent_id}" is configured for "{existing_model}", '
                f'expected "{model["model_id"]}"'
            )
        return agent_id

    result = run_openclaw_command(
        [
            "agents",
            "add",
            agent_id,
            "--workspace",
            workspace,
            "--model",
            model["model_id"],
            "--non-interactive",
            "--json",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "openclaw agents add failed")

    return agent_id


def build_openclaw_prompt(evaluation_payload: dict, decision_schema: dict):
    allowed_reason_codes = decision_schema.get("reason_codes", [])
    prompt = {
        "task": "Evaluate this paper-only Set & Forget tournament snapshot.",
        "rules": [
            "Use only the provided objective snapshot.",
            "Do not mention broker execution or live trading.",
            "Return JSON only with decision, confidence_score, reason_codes, summary.",
            "decision must be one of BUY, SELL, WAIT, NO-GO.",
            "confidence_score must be an integer between 0 and 100.",
            "reason_codes must contain 1 to 4 items from the allowed list.",
            "summary must be a short plain-language explanation.",
        ],
        "allowed_reason_codes": allowed_reason_codes,
        "evaluation_payload": evaluation_payload,
    }
    return json.dumps(prompt, indent=2, ensure_ascii=False)


def parse_model_response_json(text: str):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].lstrip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(cleaned[start:end + 1])


def normalize_model_output(raw_output: dict, decision_schema: dict):
    if not isinstance(raw_output, dict):
        return build_openclaw_error_output("OpenClaw model output must be a JSON object.")

    decision = raw_output.get("decision")
    confidence_score = raw_output.get("confidence_score")
    reason_codes = raw_output.get("reason_codes")
    summary = raw_output.get("summary")

    if decision not in ALLOWED_DECISIONS:
        return build_openclaw_error_output(f"OpenClaw model returned invalid decision: {decision!r}.")

    if not isinstance(confidence_score, int) or isinstance(confidence_score, bool):
        return build_openclaw_error_output("OpenClaw model returned a non-integer confidence_score.")

    if confidence_score < 0 or confidence_score > 100:
        return build_openclaw_error_output("OpenClaw model returned confidence_score outside 0-100.")

    if not isinstance(reason_codes, list) or not reason_codes:
        return build_openclaw_error_output("OpenClaw model returned empty reason_codes.")

    if len(reason_codes) > 4:
        return build_openclaw_error_output("OpenClaw model returned more than 4 reason_codes.")

    if any(not isinstance(code, str) or not code.strip() for code in reason_codes):
        return build_openclaw_error_output("OpenClaw model returned invalid reason_codes entries.")

    allowed_reason_codes = set(decision_schema.get("reason_codes", []))
    unknown_reason_codes = [code for code in reason_codes if code not in allowed_reason_codes]
    if unknown_reason_codes:
        return build_openclaw_error_output(
            "OpenClaw model returned unknown reason_codes: " + ", ".join(unknown_reason_codes)
        )

    if not isinstance(summary, str) or not summary.strip():
        return build_openclaw_error_output("OpenClaw model returned an empty summary.")

    return {
        "decision": decision,
        "confidence_score": confidence_score,
        "reason_codes": [code.strip() for code in reason_codes],
        "summary": summary.strip(),
    }


def evaluate_with_openclaw(model: dict, evaluation_payload: dict, primary_payload: dict, decision_schema: dict):
    del primary_payload
    if shutil.which(get_openclaw_command()[0]) is None:
        return build_openclaw_error_output("openclaw CLI is not available in PATH.")

    try:
        agent_id = ensure_openclaw_agent(model)
    except RuntimeError as exc:
        return build_openclaw_error_output(f"OpenClaw agent setup failed: {exc}")

    result = run_openclaw_command(
        [
            "agent",
            "--agent",
            agent_id,
            "--message",
            build_openclaw_prompt(evaluation_payload, decision_schema),
            "--timeout",
            str(get_openclaw_timeout_seconds()),
            "--json",
        ]
    )
    if result.returncode != 0:
        error_detail = result.stderr.strip() or result.stdout.strip() or "unknown OpenClaw error"
        return build_openclaw_error_output(f"OpenClaw agent call failed: {error_detail}")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return build_openclaw_error_output(f"OpenClaw agent returned invalid JSON envelope: {exc}")

    text_payloads = payload.get("result", {}).get("payloads", [])
    first_text = text_payloads[0].get("text") if text_payloads and isinstance(text_payloads[0], dict) else None
    if not isinstance(first_text, str) or not first_text.strip():
        return build_openclaw_error_output("OpenClaw agent response did not contain a text payload.")

    try:
        parsed_output = parse_model_response_json(first_text)
    except json.JSONDecodeError as exc:
        return build_openclaw_error_output(f"OpenClaw model text was not valid JSON: {exc}")

    return normalize_model_output(parsed_output, decision_schema)


def apply_hard_gate_policy(model_output: dict, primary_payload: dict):
    actionable = model_output["decision"] in {"BUY", "SELL"}
    primary_blocking = primary_payload["decision"] in {"WAIT", "NO-GO"}

    if not actionable or not primary_blocking:
        return {
            **model_output,
            "hard_gate_respected": True,
            "policy_enforced": False,
        }

    return {
        "decision": primary_payload["decision"],
        "confidence_score": min(model_output["confidence_score"], primary_payload["confidence_score"]),
        "reason_codes": list(primary_payload["reason_codes"]),
        "summary": (
            f"{model_output['summary']} | Hard gate policy enforced; "
            f"primary engine remains {primary_payload['decision']}."
        ),
        "hard_gate_respected": True,
        "policy_enforced": True,
    }


def build_tournament_entry(run_id: str, feature_snapshot: dict, model: dict, primary_payload: dict, evaluated_output: dict):
    meta = feature_snapshot["meta"]
    return {
        "tournament_entry_version": "1.0",
        "run_id": run_id,
        "recorded_at": timestamp_now(),
        "model_id": model["model_id"],
        "adapter": model["adapter"],
        "pair": meta["pair"],
        "execution_timeframe": meta["execution_timeframe"],
        "execution_mode": meta["execution_mode"],
        "primary_decision": primary_payload["decision"],
        "decision": evaluated_output["decision"],
        "confidence_score": evaluated_output["confidence_score"],
        "objective_only": True,
        "hard_gate_respected": evaluated_output["hard_gate_respected"],
        "policy_enforced": evaluated_output["policy_enforced"],
        "reason_codes": evaluated_output["reason_codes"],
        "summary": evaluated_output["summary"],
    }


def run_tournament(
    *,
    feature_snapshot: dict,
    feature_schema: dict,
    models_manifest: dict,
    output_schema: dict,
    skill: dict,
    decision_schema: dict,
    runs_dir: Path,
    tournament_log: Path,
    run_label: str | None = None,
    model_decision_runner=None,
):
    runtime_env.load_standardized_env(BASE_DIR)
    feature_errors = feature_snapshot_module.validate_feature_snapshot(feature_snapshot, feature_schema)
    if feature_errors:
        return {
            "status": "invalid_feature_snapshot",
            "errors": feature_errors,
            "entries": [],
        }, 1

    manifest_errors = validate_models_manifest(models_manifest)
    if manifest_errors:
        return {
            "status": "invalid_models_manifest",
            "errors": manifest_errors,
            "entries": [],
        }, 1

    primary_payload, primary_exit_code = build_primary_payload(feature_snapshot, skill, decision_schema)
    if primary_exit_code != 0:
        return {
            "status": "invalid_primary_baseline",
            "errors": primary_payload["validation"]["errors"],
            "primary_payload": primary_payload,
            "entries": [],
        }, 1

    evaluation_payload = feature_snapshot_module.build_openclaw_evaluation_payload(feature_snapshot, decision_schema)
    timestamp_token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    pair = feature_snapshot["meta"]["pair"].lower()
    run_id = f"{timestamp_token}_openclaw_tournament_{pair}"
    if run_label:
        run_id = f"{run_id}_{run_label}"

    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    feature_snapshot_path = run_dir / "feature_snapshot.json"
    primary_payload_path = run_dir / "primary_decision.json"
    tournament_entries_path = run_dir / "tournament_entries.json"
    evaluation_payload_path = run_dir / "openclaw_evaluation_payload.json"

    entries = []
    model_decision_runner = model_decision_runner or evaluate_with_openclaw
    for model in models_manifest["models"]:
        raw_output = model_decision_runner(model, evaluation_payload, primary_payload, decision_schema)
        evaluated_output = apply_hard_gate_policy(raw_output, primary_payload)
        entry = build_tournament_entry(run_id, feature_snapshot, model, primary_payload, evaluated_output)
        entry_errors = validate_tournament_entry(entry, output_schema)
        if entry_errors:
            return {
                "status": "invalid_tournament_entry",
                "errors": entry_errors,
                "model_id": model["model_id"],
                "entries": entries,
            }, 1
        entries.append(entry)

    feature_snapshot_path.write_text(json.dumps(feature_snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    primary_payload_path.write_text(json.dumps(primary_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tournament_entries_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    evaluation_payload_path.write_text(json.dumps(evaluation_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    append_jsonl(tournament_log, entries)

    return {
        "status": "completed",
        "run": {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "feature_snapshot_path": str(feature_snapshot_path),
            "primary_payload_path": str(primary_payload_path),
            "tournament_entries_path": str(tournament_entries_path),
            "evaluation_payload_path": str(evaluation_payload_path),
            "tournament_log_path": str(tournament_log),
            "model_count": len(entries),
        },
        "primary_payload": primary_payload,
        "entries": entries,
    }, 0


def render_text_report(result: dict):
    if result["status"] != "completed":
        lines = [f"OPENCLAW TOURNAMENT STATUS: {result['status']}"]
        for error in result.get("errors", []):
            lines.append(f"- {error}")
        return "\n".join(lines)

    lines = [
        "=" * 100,
        "OPENCLAW TOURNAMENT",
        f"Run ID: {result['run']['run_id']}",
        (
            f"Primary baseline: decision={result['primary_payload']['decision']} "
            f"confidence={result['primary_payload']['confidence_score']}"
        ),
    ]
    for entry in result["entries"]:
        lines.append(
            f"- {entry['model_id']} ({entry['adapter']}): "
            f"decision={entry['decision']} confidence={entry['confidence_score']} "
            f"policy_enforced={entry['policy_enforced']}"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run a local OpenClaw-style tournament on one feature snapshot.")
    parser.add_argument("--feature-snapshot-file", type=Path, default=FEATURE_SNAPSHOT_FILE)
    parser.add_argument("--feature-schema-file", type=Path, default=FEATURE_SNAPSHOT_SCHEMA_FILE)
    parser.add_argument("--models-file", type=Path, default=MODELS_FILE)
    parser.add_argument("--output-schema-file", type=Path, default=OUTPUT_SCHEMA_FILE)
    parser.add_argument("--skill-file", type=Path, default=SKILL_FILE)
    parser.add_argument("--decision-schema-file", type=Path, default=DECISION_SCHEMA_FILE)
    parser.add_argument("--runs-dir", type=Path, default=TOURNAMENT_RUNS_DIR)
    parser.add_argument("--tournament-log", type=Path, default=TOURNAMENT_LOG_FILE)
    parser.add_argument("--run-label", default=None)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    result, exit_code = run_tournament(
        feature_snapshot=load_json(args.feature_snapshot_file),
        feature_schema=load_json(args.feature_schema_file),
        models_manifest=load_json(args.models_file),
        output_schema=load_json(args.output_schema_file),
        skill=load_json(args.skill_file),
        decision_schema=load_json(args.decision_schema_file),
        runs_dir=args.runs_dir,
        tournament_log=args.tournament_log,
        run_label=args.run_label,
    )

    if args.format == "text":
        print(render_text_report(result))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
