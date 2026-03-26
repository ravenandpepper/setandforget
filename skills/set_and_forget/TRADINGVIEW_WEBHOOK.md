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
- trigger-only route: `/webhooks/tradingview/trigger-only`
- health route: `/healthz`

Voor een extern bereikbare VPS-setup hoort hier later nog een reverse proxy of service-laag voor poort `80` of `443` bovenop te komen.

## Cybersecure VPS route

De kleinste veilige VPS-opzet is:

1. laat de bestaande Python server alleen op `127.0.0.1:8787` draaien
2. publiceer alleen een geheime publieke route via een reverse proxy op poort `80` of `443`
3. allowlist in die proxy alleen de TradingView webhook IP's
4. laat `/healthz` alleen lokaal bereikbaar blijven

Versieerde deploy artefacten:

- systemd user unit: [deploy/systemd/setandforget-tradingview-webhook.service](/Users/jeroenderaaf/Sites/setandforget/deploy/systemd/setandforget-tradingview-webhook.service)
- VPS install script: [scripts/install_tradingview_webhook_service_vps.sh](/Users/jeroenderaaf/Sites/setandforget/scripts/install_tradingview_webhook_service_vps.sh)
- nginx voorbeeldconfig: [deploy/nginx/setandforget-tradingview-webhook.conf.example](/Users/jeroenderaaf/Sites/setandforget/deploy/nginx/setandforget-tradingview-webhook.conf.example)

De nginx voorbeeldconfig gebruikt bewust:

- een localhost upstream naar `127.0.0.1:8787`
- `POST`-only webhook locations
- een geheim padsegment `REPLACE_WITH_LONG_RANDOM_TOKEN`
- allowlisting voor de TradingView source IP's
- een niet-publieke health route

Na het vervangen van `REPLACE_WITH_LONG_RANDOM_TOKEN` wordt de publieke trigger-only URL:

`http://38.242.214.188/webhooks/tradingview/REPLACE_WITH_LONG_RANDOM_TOKEN/trigger-only`

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
- [tradingview_trigger_only_alert.example.json](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/tradingview_trigger_only_alert.example.json)
- [tradingview_trigger_only_alert_message_template.txt](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/tradingview_trigger_only_alert_message_template.txt)
- [tradingview_trigger_only_webhook.pine](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/tradingview_trigger_only_webhook.pine)
- [tradingview_candle_bundle_alert.pine](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/tradingview_candle_bundle_alert.pine)

## Trigger-only alert setup

Voor de publiek bereikbare VPS-route is nu juist de `trigger_only` flow het beoogde startpunt:

1. Open in TradingView de chart waarop je de alert wilt laten afgaan.
2. Maak een alert op candle close voor je bestaande triggerconditie.
3. Zet de webhook URL op je actieve geheime VPS endpoint, bijvoorbeeld:
   - `http://38.242.214.188/webhooks/tradingview/REPLACE_WITH_LONG_RANDOM_TOKEN/trigger-only`
4. Plak als alert message de template uit:
   - [tradingview_trigger_only_alert_message_template.txt](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/tradingview_trigger_only_alert_message_template.txt)
5. Gebruik deze route alleen voor paper trading of advisory mode.

Belangrijke nuances:

- de server canonicaliseert `pair` uit `{{ticker}}`, dus `PEPPERSTONE:EURUSD` wordt intern `EURUSD`
- `{{interval}}` mag `240` zijn; de ingest normaliseert dat intern naar `4H`
- een externe handmatige `curl` vanaf je eigen IP mag op deze publieke route `403 Forbidden` geven; dat bevestigt juist de nginx allowlist
- de huidige trigger-only Pine en template zetten `news_context_enabled` nu standaard op `true`, zodat de VPS Brave risk-context kan meenemen
- bestaande TradingView alerts nemen die nieuwe default niet vanzelf altijd over; open ze na de script-update opnieuw en sla ze opnieuw op

## Trigger-only Pine startpunt

Voor de TradingView-native trigger-only route staat nu ook een Pine script klaar:

- [tradingview_trigger_only_webhook.pine](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/tradingview_trigger_only_webhook.pine)

Wat dit script doet:

- draait bedoeld op een `4H` chart
- verstuurt de `trigger_only` webhook payload via `alert()` op candle close
- toont op `W`- en `D`-charts rechtsboven alleen een eenvoudige objectieve trendstatus: `Bullish`, `Bearish` of `Neutral`
- toont op de `4H` chart een subtiele marker zodat je ziet dat de alert-context actief is zonder een apart blauw paneel

De trendbox gebruikt bewust een eenvoudige, explainable definitie:

- `Bullish`: laatst gesloten candle close > open
- `Bearish`: laatst gesloten candle close < open
- `Neutral`: laatst gesloten candle close = open

Deze box verandert niets aan de server-side beslislogica. Hij is alleen bedoeld om je zondagselectie en chart-screening sneller te maken.

Gebruik in TradingView voor deze Pine-variant:

1. Voeg de indicator toe aan de chart.
2. Maak een alert op `Any alert() function call`.
3. Zet als webhook URL je VPS endpoint.
4. Laat het alert message veld leeg, omdat `alert()` zelf de JSON payload bouwt.

## Eerste live test

Na het opslaan van de TradingView alert is de kleinste productietest:

1. Verstuur één echte alert vanuit TradingView naar de publieke `trigger-only` route.
2. Controleer direct daarna op de VPS:
   - `journalctl --user -u setandforget-tradingview-webhook.service -n 50 --no-pager`
3. Verwachte webhook-uitkomst bij succes:
   - HTTP `200`
   - response `status: "processed"`
   - `market_data_fetch.status: "prepared"`
   - `automation.run.trigger: "tradingview_trigger_only"`
4. Bij een niet-geldige payload verwacht je geen `403`, maar een applicatie-response zoals `400` of `422`.

Aanvullende controlepunten:

- als inference vanuit de huidige service-unit en Python defaults: paper trades landen normaal in `/home/traderops/setandforget/skills/set_and_forget/paper_trades_log.jsonl`
- als inference vanuit dezelfde defaults: automation-beslissingen landen normaal in `/home/traderops/setandforget/skills/set_and_forget/automation_decisions_log.jsonl`
- de trigger-only flow blijft server-side candles ophalen; TradingView is dus alleen de triggerbron, niet de bron van strategielogica

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
