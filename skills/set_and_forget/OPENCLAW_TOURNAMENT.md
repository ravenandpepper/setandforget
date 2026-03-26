# OpenClaw Tournament Plan

Dit document bewaart het gewenste eindbeeld voor een OpenClaw-gestuurde multi-model tournament-laag bovenop de bestaande Set & Forget engine.

## Doel

Het doel is niet om LLM's direct broker-orders te laten versturen.
Het doel is om meerdere modellen exact dezelfde objectieve marktsituatie te laten beoordelen, hun prestaties in paper mode te vergelijken en pas later gecontroleerd iets naar live execution te promoveren.

## Leidende regels

- Set & Forget blijft de primaire source of truth.
- Hard gates van de primaire engine blijven niet-overridebaar.
- `fxalex` blijft advisory only.
- `news_context` blijft risk context only.
- LLM's mogen alleen evalueren op objectieve `feature_snapshot` data.
- Broker execution blijft deterministisch en gescheiden van model-analyse.

## Gewenst eindbeeld

De beoogde pipeline wordt:

1. TradingView trigger
2. webhook ingest
3. marktdata + feature extraction
4. primaire Set & Forget evaluatie
5. OpenClaw tournament-run op exact dezelfde `feature_snapshot`
6. per model een paper verdict en shadow portfolio update
7. leaderboard en dashboard
8. pas later eventueel promotion naar gecontroleerde broker execution

## OpenClaw-rol

OpenClaw is in dit ontwerp de regisseur van de tournament-laag:

- dezelfde input naar meerdere modellen sturen
- model-output valideren tegen een vast contract
- resultaten loggen
- score- en leaderboardberekeningen starten
- later eventueel een promotion-policy toepassen

OpenClaw is in dit ontwerp dus niet de broker zelf.

## Modelbeleid

Elke deelnemer krijgt exact dezelfde input en moet exact hetzelfde outputcontract volgen:

- `decision`
- `confidence_score`
- `reason_codes`
- `summary`

Optioneel later:

- `entry_adjustment`
- `risk_comment`

Modellen concurreren op analysekwaliteit en paper performance.
Niet op directe order-submissie.

## Tournament-opzet

Per model wil je minstens deze dingen loggen:

- model-id
- timestamp
- pair
- timeframe
- feature snapshot id
- primary decision
- model decision
- confidence
- redencodes
- final paper outcome
- PnL
- drawdown impact

Daarnaast wil je een baseline behouden:

- pure Set & Forget baseline
- per model een eigen shadow portfolio

## Dashboard-doelen

Het dashboard komt later, maar moet uiteindelijk minimaal tonen:

- equity curve per model
- leaderboard per 7 dagen, 30 dagen en all-time
- baseline versus modelperformance
- recente decisions
- model agreement/disagreement
- prestaties per marktcluster
- redenen waarom hard gates een trade blokkeerden

## Pepperstone-rol

Pepperstone hoort pas later in beeld te komen.
Tot die tijd blijft execution:

- paper only
- dry run
- policy gated

Live execution mag pas een vervolgstap zijn nadat:

- de tournament-logging stabiel is
- de baseline vergelijkbaar is
- sample size groot genoeg is
- promotion-regels expliciet zijn vastgelegd

## Eerste stap

De eerste stap is niet het dashboard en niet live Pepperstone.

De eerste stap is:

een vast `model tournament contract` bouwen voor OpenClaw.

Concreet betekent dat:

1. één inputcontract op basis van `feature_snapshot`
2. één outputcontract voor alle modellen
3. één runner die meerdere modellen op dezelfde snapshot laat evalueren
4. één append-only log waarin alle model-uitkomsten uniform worden weggeschreven

Zonder deze stap is een leaderboard of dashboard nog niet betrouwbaar.

## Huidige implementatie in deze repo

De tournament-runner gebruikt nu echte OpenClaw agent-calls voor vier OpenRouter-modellen:

- Minimax M1
- Claude Sonnet 4.6
- Claude Opus 4.6
- Kimi K2

Bestanden:

- [openclaw_tournament.py](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/openclaw_tournament.py)
- [openclaw_tournament_output_schema.json](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/openclaw_tournament_output_schema.json)
- [openclaw_tournament_models.example.json](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/openclaw_tournament_models.example.json)
- [run_openclaw_tournament_tests.py](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/run_openclaw_tournament_tests.py)

Wat deze iteratie bewust wel doet:

- exact dezelfde `feature_snapshot` naar meerdere OpenClaw/OpenRouter models sturen
- primary Set & Forget baseline naast alle model-uitkomsten loggen
- hard gates van de primary engine non-overridable houden
- append-only tournament logging wegschrijven

Wat deze iteratie bewust nog niet doet:

- scoring op gerealiseerde PnL
- dashboard rendering
