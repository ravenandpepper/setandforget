# Structured Automation

Deze laag voegt alleen een scheduler-facing wrapper toe bovenop de bestaande Set & Forget decision engine. De strategy logic blijft in `run_set_and_forget.py`, `fxalex` blijft advisory only en paper trading blijft de enige execution-flow in deze iteratie.

## Entrypoint

Gebruik voor periodieke runs:

```bash
python3 skills/set_and_forget/run_structured_automation.py \
  --snapshot-file skills/set_and_forget/live_snapshot.json \
  --trigger scheduler \
  --run-label london-open
```

De wrapper hergebruikt intern `run_set_and_forget.run_decision_cycle(...)` en dupliceert geen strategy-, advisory- of paper-tradinglogica.

Voor meerdere snapshots in één automation-run is er ook een batch entrypoint:

```bash
python3 skills/set_and_forget/run_structured_automation_batch.py \
  --manifest-file /path/to/automation_manifest.json \
  --trigger scheduler-batch
```

Voorbeeld van een manifest:

```json
{
  "runs": [
    {
      "snapshot_file": "snapshots/eurusd_4h.json",
      "run_label": "eurusd-london"
    },
    {
      "snapshot_file": "snapshots/gbpusd_4h.json",
      "run_label": "gbpusd-london"
    }
  ]
}
```

Relatieve `snapshot_file` paden worden opgelost ten opzichte van de map waar het manifest staat.

## Outputflow

Per run wordt een map aangemaakt in `skills/set_and_forget/automation_runs/<run_id>/` met:

- `snapshot_in.json`: het input snapshot dat door automation is aangeboden
- `decision.json`: de finale engine-output inclusief advisory states en paper-trade metadata
- `paper_trade_ticket.json`: alleen aanwezig wanneer de finale decision `BUY` of `SELL` is en paper trading een ticket opent

Daarnaast worden twee append-only logs gebruikt:

- `skills/set_and_forget/automation_decisions_log.jsonl`: een compacte run-samenvatting per automation-cycle
- `skills/set_and_forget/paper_trades_log.jsonl`: bestaand paper-trade log, alleen voor `BUY` en `SELL`

## Gedrag

- `BUY` en `SELL` mogen de bestaande paper-trade flow gebruiken
- `WAIT` en `NO-GO` schrijven wel decision artefacten, maar openen nooit een paper trade
- De wrapper bereidt geen live execution, broker-integratie of TradingView/Pepperstone logic voor

## Scheduler-contract

Automation hoeft alleen een geldig snapshotbestand te leveren dat aan `set_and_forget_decision_schema.json` voldoet en daarna het entrypoint aan te roepen. De wrapper schrijft de artefacten weg en retourneert een JSON-resultaat dat direct door een scheduler of logcollector gebruikt kan worden.

Bij batch-runs hoeft automation alleen een manifest met snapshotpaden te leveren. Elke manifest-entry wordt daarna als een losse structured run afgehandeld, met dezelfde regels voor `BUY`, `SELL`, `WAIT` en `NO-GO`.
