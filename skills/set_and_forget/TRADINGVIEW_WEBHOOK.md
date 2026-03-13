# TradingView Webhook

Deze laag voegt een kleine HTTP webhook-ingest toe bovenop de bestaande TradingView alert adapter. De server doet geen broker-calls en geen live execution. Hij ondersteunt nu twee routes:

- `snapshot` route: TradingView of upstream levert al de Set & Forget structuurvelden aan.
- `candle_bundle` route: TradingView of upstream levert `weekly`, `daily` en `h4` candles plus objectieve risk/operational context aan. De runner leidt daarna zelf market structure af.

## Lokale start

```bash
python3 skills/set_and_forget/tradingview_webhook_server.py
```

Standaard luistert de server op:

- host: `127.0.0.1`
- port: `8787`
- webhook route: `/webhooks/tradingview`
- health route: `/healthz`

Voor een extern bereikbare VPS-setup hoort hier later nog een reverse proxy of service-laag voor poort `80` of `443` bovenop te komen.

## Testen met voorbeeldpayload

```bash
python3 skills/set_and_forget/run_tradingview_webhook.py --format text
python3 skills/set_and_forget/run_tradingview_webhook_server_tests.py
```

## Voorbeeld alert messages

Gebruik als startpunt:

- [tradingview_alert.example.json](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/tradingview_alert.example.json)
- [tradingview_candle_alert.example.json](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/tradingview_candle_alert.example.json)
- [tradingview_candle_alert_message_template.txt](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/tradingview_candle_alert_message_template.txt)
- [tradingview_candle_bundle_alert.pine](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/tradingview_candle_bundle_alert.pine)

## Candle bundle template

De nieuwe candle-route verwacht:

- `candles.weekly`
- `candles.daily`
- `candles.h4`
- `risk_features`
- `operational_flags`

In het templatebestand staan twee soorten placeholders:

- TradingView placeholders die direct kunnen blijven staan:
  - `{{ticker}}`
  - `{{exchange}}`
  - `{{interval}}`
  - `{{time}}`
- upstream placeholders die je via Pine of een andere generator moet invullen:
  - `__WEEKLY_CANDLES_JSON__`
  - `__DAILY_CANDLES_JSON__`
  - `__H4_CANDLES_JSON__`
  - risk/operational velden

Belangrijke nuance:

- TradingView native placeholders kunnen geen volledige candle-arrays genereren.
- Voor de candle-bundle route moet de alert message dus door Pine-logica of een andere upstream stap als complete JSON-string worden opgebouwd.
- Als je dat nog niet hebt, gebruik voorlopig de bestaande snapshot-route.

## Pine startpunt

Voor een eerste TradingView-native route staat er nu een Pine script klaar:

- [tradingview_candle_bundle_alert.pine](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/tradingview_candle_bundle_alert.pine)

Wat dit script doet:

- draait bedoeld op een `4H` chart
- haalt via `request.security(...)` de laatste `W`, `D` en `4H` candles op
- bouwt daaruit een `candle_bundle` webhook payload
- verstuurt die via `alert()` op candle close

Belangrijke grenzen:

- risk- en operational-velden zijn nu nog `input(...)` waarden
- `aoi_features` en `confirmation_features` worden bewust op `null` gezet, zodat onze Python market-structure laag die later objectief afleidt
- dit is een eerste Pine startpunt; nog geen volledig gevalideerde productie-indicator

Gebruik in TradingView:

1. Maak een nieuwe indicator met de inhoud van het Pine bestand.
2. Voeg hem toe aan een `4H` chart.
3. Maak een alert op `Any alert() function call`.
4. Zet als webhook URL je VPS endpoint.
5. Laat de alert message leeg, omdat `alert()` zelf de JSON payload bouwt.
