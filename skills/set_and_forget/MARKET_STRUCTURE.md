# Market Structure

Deze laag zet ruwe candles plus objectieve context om naar het bestaande `feature_snapshot` contract.

## Doel

De primaire Set & Forget engine moet uiteindelijk niet meer afhankelijk zijn van handmatig ingevulde structuurvelden. Daarom is dit de eerste deterministische candle-to-feature stap:

1. `weekly` candles analyseren
2. `daily` candles analyseren
3. `h4` pullback en reversal analyseren
4. samenvoegen met objectieve AOI-, confirmation-, risk- en operationele context
5. output als `feature_snapshot`

## Huidige scope

Deze iteratie doet alleen:

- pivot highs / lows detecteren
- trend en structure state bepalen voor `weekly` en `daily`
- `h4` pullback structure, BOS en eerste entry state afleiden
- projecteren naar het bestaande Set & Forget decision snapshot

Deze iteratie doet nog niet:

- automatische AOI detectie uit swings/fibonacci
- automatische confirmation patroonherkenning uit candles
- automatische risk sizing
- live data ingest

## Bestanden

- [market_structure_input_schema.json](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/market_structure_input_schema.json)
- [market_structure.py](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/market_structure.py)
- [market_structure_test_fixtures.json](/Users/jeroenderaaf/Sites/setandforget/skills/set_and_forget/market_structure_test_fixtures.json)

## Architectuur

De output van deze laag is bewust objectief en compact, zodat:

- de rule-engine er direct op kan draaien
- OpenClaw later meerdere LLM's exact dezelfde uitgangspositie kan geven
- tokengebruik beperkt blijft tot afgeleide features in plaats van grote candle dumps
