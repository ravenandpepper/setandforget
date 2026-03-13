# fxalex

## Purpose
This workspace skill-pack provides a secondary advisory decision layer based on the existing `fxalex` rule engine, claims voting logic, and hybrid runner. Within this project it is not the primary strategy engine. It should be used only as a confluence or confidence layer on top of the main Set & Forget strategy.

## Role In This Workspace
- `secondary`
- `advisory_only`
- `paper_mode_only`
- `cannot_override_primary_hard_gates`

## Main Files
- `fxalex_skill_v2.json`: machine-readable rule configuration
- `fxalex_decision_schema.json`: input and output contract
- `live_snapshot.json`: example snapshot for local validation
- `run_fxalex_hybrid.py`: main runner that combines rules and claims voting
- `run_fxalex_decisions.py`: rule-only local test runner
- `run_fxalex_claim_votes.py`: claims-voting local test runner
- `fxalex_knowledge_graph.json`: reasoning and concept graph

## Expected Output
The hybrid runner returns advisory output with:
- `decision`
- `confidence_score`
- `reason_codes`
- `summary`

The runner supports:
- JSON output by default
- text output via `--format text`

## Local Usage
Run the hybrid advisory layer:

```bash
python3 skills/fxalex/run_fxalex_hybrid.py
```

Run the text report:

```bash
python3 skills/fxalex/run_fxalex_hybrid.py --format text
```

## Integration Guidance
- Prefer the Set & Forget engine as the primary decision-maker.
- Use `fxalex` only after the primary engine has produced a valid advisory decision.
- Treat `fxalex` support as a bounded confidence adjustment or conflict signal.
- Never let `fxalex` flip a primary `WAIT` or `NO-GO` into `BUY` or `SELL`.
