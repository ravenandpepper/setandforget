import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import feature_snapshot as feature_snapshot_module
import model_reflection_snapshot as model_reflection_snapshot_module
import run_set_and_forget as engine
import runtime_env
import shadow_portfolio_settlement as shadow_portfolio_settlement_module


BASE_DIR = Path(__file__).resolve().parent
FEATURE_SNAPSHOT_FILE = BASE_DIR / "feature_snapshot.example.json"
FEATURE_SNAPSHOT_SCHEMA_FILE = BASE_DIR / "feature_snapshot_schema.json"
DECISION_SCHEMA_FILE = BASE_DIR / "set_and_forget_decision_schema.json"
SKILL_FILE = BASE_DIR / "set_and_forget_skill_v1.json"
MODELS_FILE = BASE_DIR / "openclaw_tournament_models.example.json"
OUTPUT_SCHEMA_FILE = BASE_DIR / "openclaw_tournament_output_schema.json"
TOURNAMENT_RUNS_DIR = BASE_DIR / "openclaw_tournament_runs"
TOURNAMENT_LOG_FILE = BASE_DIR / "openclaw_tournament_log.jsonl"
TOURNAMENT_SHADOW_PORTFOLIO_LOG_FILE = BASE_DIR / "openclaw_shadow_portfolio_log.jsonl"
TOURNAMENT_SHADOW_SETTLEMENT_LOG_FILE = BASE_DIR / "openclaw_shadow_portfolio_settlements.jsonl"
MODEL_REFLECTION_LOG_FILE = BASE_DIR / "openclaw_model_reflection_snapshots.jsonl"
ALLOWED_DECISIONS = {"BUY", "SELL", "WAIT", "NO-GO"}
DEFAULT_OPENCLAW_COMMAND = "openclaw"
DEFAULT_OPENCLAW_TIMEOUT_SECONDS = 180
DEFAULT_OPENCLAW_AGENT_PREFIX = "setandforget_tournament"
DEFAULT_OPENCLAW_SESSION_PREFIX = "setandforget_tournament"
DEFAULT_OPENCLAW_MAX_ATTEMPTS = 2


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


def load_json_rows(path: Path):
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as handle:
        rows = []
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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


def get_openclaw_max_attempts():
    raw_attempts = os.environ.get("OPENCLAW_TOURNAMENT_MAX_ATTEMPTS", str(DEFAULT_OPENCLAW_MAX_ATTEMPTS))
    try:
        return max(1, int(raw_attempts))
    except ValueError:
        return DEFAULT_OPENCLAW_MAX_ATTEMPTS


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


def load_latest_model_reflections(path: Path):
    latest = {}
    for row in load_json_rows(path):
        model_id = row.get("model_id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        previous = latest.get(model_id)
        if previous is None or row.get("generated_at", "") >= previous.get("generated_at", ""):
            latest[model_id] = row
    return latest


def build_openclaw_prompt(evaluation_payload: dict, decision_schema: dict, model_reflection_snapshot: dict | None = None):
    allowed_reason_codes = decision_schema.get("reason_code_catalog", [])
    prompt = {
        "task": "Evaluate this paper-only Set & Forget tournament snapshot.",
        "rules": [
            "Use only the provided objective snapshot.",
            "Do not mention broker execution or live trading.",
            "Treat model_reflection_snapshot as advisory self-review only, never as a replacement for the current snapshot.",
            "Do not let model_reflection_snapshot override the primary hard-gate policy.",
            "Return JSON only with decision, confidence_score, reason_codes, summary.",
            "decision must be one of BUY, SELL, WAIT, NO-GO.",
            "confidence_score must be an integer between 0 and 100.",
            "reason_codes must contain 1 to 4 items from the allowed list.",
            "summary must be a short plain-language explanation.",
        ],
        "allowed_reason_codes": allowed_reason_codes,
        "evaluation_payload": evaluation_payload,
    }
    if model_reflection_snapshot is not None:
        prompt["model_reflection_snapshot"] = model_reflection_snapshot
    return json.dumps(prompt, indent=2, ensure_ascii=False)


def build_openclaw_session_id(run_id: str, model: dict, attempt: int = 1):
    prefix = os.environ.get("OPENCLAW_TOURNAMENT_SESSION_PREFIX", DEFAULT_OPENCLAW_SESSION_PREFIX)
    model_slug = slugify(model["model_id"])
    digest = hashlib.sha1(f"{run_id}:{model_slug}:attempt:{attempt}".encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}_{model_slug}"


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

    allowed_reason_codes = set(decision_schema.get("reason_code_catalog", []))
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


def extract_first_text_payload(payload: dict):
    text_payloads = payload.get("result", {}).get("payloads", [])
    if not isinstance(text_payloads, list):
        return None

    for item in text_payloads:
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                return text
    return None


def should_retry_openclaw_error(summary: str):
    retryable_fragments = [
        "invalid JSON envelope",
        "did not contain a text payload",
        "text was not valid JSON",
        "agent call failed",
    ]
    return any(fragment in summary for fragment in retryable_fragments)


def evaluate_with_openclaw(
    model: dict,
    evaluation_payload: dict,
    primary_payload: dict,
    decision_schema: dict,
    *,
    model_reflection_snapshot: dict | None = None,
    run_id: str,
):
    del primary_payload
    if shutil.which(get_openclaw_command()[0]) is None:
        return build_openclaw_error_output("openclaw CLI is not available in PATH.")

    try:
        agent_id = ensure_openclaw_agent(model)
    except RuntimeError as exc:
        return build_openclaw_error_output(f"OpenClaw agent setup failed: {exc}")

    last_error = None
    for attempt in range(1, get_openclaw_max_attempts() + 1):
        session_id = build_openclaw_session_id(run_id, model, attempt)
        result = run_openclaw_command(
            [
                "agent",
                "--agent",
                agent_id,
                "--session-id",
                session_id,
                "--message",
                build_openclaw_prompt(evaluation_payload, decision_schema, model_reflection_snapshot),
                "--timeout",
                str(get_openclaw_timeout_seconds()),
                "--json",
            ]
        )
        if result.returncode != 0:
            error_detail = result.stderr.strip() or result.stdout.strip() or "unknown OpenClaw error"
            last_error = build_openclaw_error_output(f"OpenClaw agent call failed: {error_detail}")
            if attempt < get_openclaw_max_attempts() and should_retry_openclaw_error(last_error["summary"]):
                continue
            return last_error

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            last_error = build_openclaw_error_output(f"OpenClaw agent returned invalid JSON envelope: {exc}")
            if attempt < get_openclaw_max_attempts():
                continue
            return last_error

        first_text = extract_first_text_payload(payload)
        if not isinstance(first_text, str) or not first_text.strip():
            last_error = build_openclaw_error_output("OpenClaw agent response did not contain a text payload.")
            if attempt < get_openclaw_max_attempts():
                continue
            return last_error

        try:
            parsed_output = parse_model_response_json(first_text)
        except json.JSONDecodeError as exc:
            last_error = build_openclaw_error_output(f"OpenClaw model text was not valid JSON: {exc}")
            if attempt < get_openclaw_max_attempts():
                continue
            return last_error

        return normalize_model_output(parsed_output, decision_schema)

    return last_error or build_openclaw_error_output("OpenClaw model evaluation failed after retries.")


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


def build_shadow_portfolio_ticket(entry: dict, feature_snapshot: dict):
    risk = feature_snapshot["risk_features"]
    actionable = entry["decision"] in {"BUY", "SELL"}
    return {
        "shadow_ticket_version": "1.0",
        "logged_at": timestamp_now(),
        "run_id": entry["run_id"],
        "model_id": entry["model_id"],
        "portfolio_key": slugify(entry["model_id"]),
        "pair": entry["pair"],
        "execution_timeframe": entry["execution_timeframe"],
        "execution_mode": entry["execution_mode"],
        "decision": entry["decision"],
        "primary_decision": entry["primary_decision"],
        "entry_price": risk.get("entry_price"),
        "stop_loss_price": risk.get("stop_loss_price"),
        "take_profit_price": risk.get("take_profit_price"),
        "risk_reward_ratio": risk["risk_reward_ratio"],
        "planned_risk_percent": risk["planned_risk_percent"],
        "confidence_score": entry["confidence_score"],
        "reason_codes": list(entry["reason_codes"]),
        "summary": entry["summary"],
        "hard_gate_respected": entry["hard_gate_respected"],
        "policy_enforced": entry["policy_enforced"],
        "shadow_trade_opened": actionable,
        "outcome_status": "pending" if actionable else "not_opened",
        "realized_pnl_r": None,
        "realized_pnl_percent": None,
        "closed_at": None,
    }


def maybe_run_post_tournament_pipeline(
    *,
    feature_snapshot: dict,
    run_dir: Path,
    shadow_portfolio_tickets: list[dict],
    shadow_portfolio_log: Path,
    settlement_log: Path,
    reflection_log: Path,
    settlement_candles_file: Path | None,
):
    if settlement_candles_file is None:
        return None

    candles_payload = shadow_portfolio_settlement_module.load_json(settlement_candles_file)
    candles = shadow_portfolio_settlement_module.extract_h4_candles(
        candles_payload,
        pair=feature_snapshot["meta"]["pair"],
        timeframe=feature_snapshot["meta"]["execution_timeframe"],
    )
    settlements_output_file = run_dir / "shadow_portfolio_settlements.json"
    settlement_result = shadow_portfolio_settlement_module.run_shadow_portfolio_settlement(
        shadow_tickets=shadow_portfolio_tickets,
        candles=candles,
        settlement_log=settlement_log,
        settlements_output_file=settlements_output_file,
    )

    reflection_output_file = run_dir / "model_reflection_snapshot.json"
    reflection_result = model_reflection_snapshot_module.run_model_reflection_snapshot(
        tickets=load_json_rows(shadow_portfolio_log),
        settlements=shadow_portfolio_settlement_module.load_json_rows(settlement_log),
        reflection_log=reflection_log,
        output_file=reflection_output_file,
    )

    return {
        "settlement": settlement_result,
        "reflection": reflection_result,
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
    shadow_portfolio_log: Path = TOURNAMENT_SHADOW_PORTFOLIO_LOG_FILE,
    settlement_log: Path = TOURNAMENT_SHADOW_SETTLEMENT_LOG_FILE,
    reflection_log: Path = MODEL_REFLECTION_LOG_FILE,
    settlement_candles_file: Path | None = None,
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
    reflection_by_model = load_latest_model_reflections(reflection_log)
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
    shadow_portfolio_tickets_path = run_dir / "shadow_portfolio_tickets.json"

    entries = []
    model_decision_runner = model_decision_runner or evaluate_with_openclaw
    for model in models_manifest["models"]:
        raw_output = model_decision_runner(
            model,
            evaluation_payload,
            primary_payload,
            decision_schema,
            model_reflection_snapshot=reflection_by_model.get(model["model_id"]),
            run_id=run_id,
        )
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

    shadow_portfolio_tickets = [
        build_shadow_portfolio_ticket(entry, feature_snapshot)
        for entry in entries
    ]
    feature_snapshot_path.write_text(json.dumps(feature_snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    primary_payload_path.write_text(json.dumps(primary_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tournament_entries_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    evaluation_payload_path.write_text(json.dumps(evaluation_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    shadow_portfolio_tickets_path.write_text(
        json.dumps(shadow_portfolio_tickets, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    append_jsonl(tournament_log, entries)
    append_jsonl(shadow_portfolio_log, shadow_portfolio_tickets)
    post_run = maybe_run_post_tournament_pipeline(
        feature_snapshot=feature_snapshot,
        run_dir=run_dir,
        shadow_portfolio_tickets=shadow_portfolio_tickets,
        shadow_portfolio_log=shadow_portfolio_log,
        settlement_log=settlement_log,
        reflection_log=reflection_log,
        settlement_candles_file=settlement_candles_file,
    )

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
            "shadow_portfolio_tickets_path": str(shadow_portfolio_tickets_path),
            "shadow_portfolio_log_path": str(shadow_portfolio_log),
            "shadow_settlement_log_path": str(settlement_log),
            "reflection_log_path": str(reflection_log),
            "model_count": len(entries),
        },
        "primary_payload": primary_payload,
        "entries": entries,
        "shadow_portfolio_tickets": shadow_portfolio_tickets,
        "post_run": post_run,
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
    parser.add_argument("--shadow-portfolio-log", type=Path, default=TOURNAMENT_SHADOW_PORTFOLIO_LOG_FILE)
    parser.add_argument("--shadow-settlement-log", type=Path, default=TOURNAMENT_SHADOW_SETTLEMENT_LOG_FILE)
    parser.add_argument("--reflection-log", type=Path, default=MODEL_REFLECTION_LOG_FILE)
    parser.add_argument("--settlement-candles-file", type=Path, default=None)
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
        shadow_portfolio_log=args.shadow_portfolio_log,
        settlement_log=args.shadow_settlement_log,
        reflection_log=args.reflection_log,
        settlement_candles_file=args.settlement_candles_file,
        run_label=args.run_label,
    )

    if args.format == "text":
        print(render_text_report(result))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
