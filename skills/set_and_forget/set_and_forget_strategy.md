# Set & Forget Swing Strategy

## Doel
Deze strategie is de primaire decision engine voor OpenClaw binnen dit project. Het doel is om 1-3 kwalitatieve swing trades per week te selecteren in `paper` of `advisory` mode, met maximaal 1-2% risico per trade.

## Kernprincipe
- Trade wat je ziet, niet wat je denkt.
- Handel alleen in de richting van de hogere trend.
- Zoek entries alleen op logische retracements met bevestiging.
- Geen setup betekent geen trade.

## Top-Down Structuur
De engine werkt altijd van hoog naar laag tijdframe:

1. `Weekly`
- Bepaalt de hoofdrichting: bullish of bearish.

2. `Daily`
- Moet dezelfde richting bevestigen als Weekly.
- Bij conflict tussen Weekly en Daily is er geen trade.

3. `4H`
- Moet eerst een tegenbeweging laten zien ten opzichte van de hogere trend.
- Daarna moet 4H terugdraaien in de richting van Weekly en Daily.
- Entry is alleen geldig op de eerste `HL` na bullish draai of de eerste `LH` na bearish draai.

## A+ Setup Definitie
### Bullish swing
- Weekly bullish
- Daily bullish
- 4H pullback bearish (`LL + LH`)
- 4H breekt terug omhoog
- 4H maakt `HH`, daarna eerste `HL`
- Entry alleen binnen een geldige AOI met candle-close bevestiging

### Bearish swing
- Weekly bearish
- Daily bearish
- 4H pullback bullish (`HH + HL`)
- 4H breekt terug omlaag
- 4H maakt `LL`, daarna eerste `LH`
- Entry alleen binnen een geldige AOI met candle-close bevestiging

## AOI Regels
Een AOI is alleen geldig als prijs in de `50%-61.8%` retracement-zone zit en er minimaal drie confluence-elementen aanwezig zijn:

- support/resistance
- order block
- structureel draaipunt

Zonder geldige AOI geen entry.

## Entry Regels
Entry is pas toegestaan als:

- Weekly en Daily aligned zijn
- 4H eerst een pullback tegen de hogere trend laat zien
- 4H daarna weer draait in de richting van de hogere trend
- de eerste `HL` of `LH` na de draai aanwezig is
- confirmation aanwezig is na candle-close

Toegestane confirmations:
- bullish engulfing
- bearish engulfing
- hammer
- shooting star
- break of structure retest

## Risk Regels
- `planned_risk_percent` mag nooit boven `2.0` uitkomen
- `risk_reward_ratio` moet minimaal `2.0` zijn
- stop-loss moet onder de laatste swing of achter de `78.6%` retracement liggen
- maximaal `2` open trades tegelijk

## Operationele Blokkades
Geen trade bij:
- Weekly en Daily misalignment
- ontbrekende of onduidelijke 4H pullback
- geen bevestigde 4H draai
- entry niet op eerste `HL` of `LH`
- AOI buiten fib-zone of minder dan 3 confluences
- ontbrekende confirmation
- belangrijk nieuws op komst
- buiten Londen-New York overlap
- set-and-forget niet uitvoerbaar

## Output Contract
De engine moet altijd teruggeven:
- `decision`
- `confidence_score`
- `reason_codes`
- `summary`

Toegestane decisions:
- `BUY`
- `SELL`
- `WAIT`
- `NO-GO`

## Relatie met fxalex
`fxalex` is expliciet geen primaire logica. De fxalex layer mag later alleen als secundaire confidence/confluence advisory worden toegevoegd en mag nooit een hard gate van deze strategie overrulen.
