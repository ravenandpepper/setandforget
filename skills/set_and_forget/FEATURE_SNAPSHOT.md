# Feature Snapshot

Deze laag legt een objectief, token-zuinig contract vast tussen marktdata, de bestaande Set & Forget rule-engine en latere OpenClaw LLM orchestration.

## Doel

Het contract is bedoeld om per evaluatiemoment alleen compacte, afgeleide marktfeatures door te geven in plaats van:

- lange documentatie mee te sturen
- grote ruwe candledumps mee te sturen
- vrije interpretatieve prompts te gebruiken

Daardoor blijft de primaire analyse objectief en blijft het tokengebruik beperkt.

## Kernidee

De pipeline wordt hiermee:

1. ruwe marktdata
2. deterministische feature extraction
3. `feature_snapshot`
4. projectie naar de bestaande Set & Forget rule-engine
5. optionele OpenClaw multi-LLM evaluatie op exact dezelfde objectieve feature set

## Belangrijke regel

Een LLM mag hier later alleen werken op gestructureerde objectieve data.
Niet op vrije chartbeschrijvingen en niet op losse trader-interpretaties.

## Bestanden

- [feature_snapshot_schema.json](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/feature_snapshot_schema.json)
- [feature_snapshot.example.json](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/feature_snapshot.example.json)
- [feature_snapshot.py](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/feature_snapshot.py)
- [OPENCLAW_TOURNAMENT.md](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/OPENCLAW_TOURNAMENT.md)

## Wat hierin zit

- `meta`: bron, pair, timeframe, mode
- `timeframe_features`: objectieve states voor `weekly`, `daily`, `h4`
- `aoi_features`
- `confirmation_features`
- `risk_features`
- `operational_flags`

## Waarom dit token-zuinig is

Een LLM hoeft later niet elke run opnieuw alle strategie-documentatie en candles te krijgen. In plaats daarvan kan OpenClaw werken met:

- één compact `feature_snapshot`
- het bestaande decision output contract
- een vaste hard-gate policy

## Huidige status

- het contract projecteert al naar het bestaande `set_and_forget_decision_schema.json`
- de huidige rule-engine kan dus later op dezelfde featurebron blijven draaien
- de marktstructuur-extractie uit ruwe candles moet nog apart worden gebouwd
