# TradingView Webhook

Deze laag voegt een kleine HTTP webhook-ingest toe bovenop de bestaande TradingView alert adapter. De server doet geen candle-analyse, geen broker-calls en geen live execution. Hij accepteert alleen een alert payload die al de vereiste Set & Forget structuurvelden bevat, zet die om naar het snapshot-contract en roept daarna de bestaande decision/automation flow aan.

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

## Voorbeeld alert message

Gebruik als startpunt:

- [tradingview_alert.example.json](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/tradingview_alert.example.json)

Dat JSON-contract is bedoeld als `application/json` alert body vanuit TradingView. De relevante velden voor marktstructuur moeten upstream al zijn bepaald, bijvoorbeeld via Pine-logica of een aparte preprocessing-stap.
