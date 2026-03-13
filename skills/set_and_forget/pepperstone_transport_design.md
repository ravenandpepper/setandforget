# Pepperstone Transport Design

## Doel

Deze stap ontwerpt de echte Pepperstone transport/interface-laag bovenop de bestaande `future_execution` scaffold, zonder broker-calls of live execution toe te voegen.

De ontwerpdoelen zijn:

- Hergebruik van de bestaande Set & Forget `order_intent`
- Duidelijke scheiding tussen config, mapping, transport en adapterlogica
- Paper-first en explicit opt-in voor alles wat richting execution gaat
- Kleine, testbare modules met voorspelbare fouten

## Scope

In scope:

- Interface-contracten
- Modulegrenzen
- Datamodellen voor request/response
- Safety gates voor paper-only en disabled transport

Niet in scope:

- Echte HTTP-calls
- Broker authenticatie
- Order placement
- TradingView webhook implementatie

## Voorgestelde modules

Plaats deze modules in `skills/set_and_forget/`:

- `pepperstone_config.py`
  Verantwoordelijk voor het lezen en valideren van Pepperstone runtime-config uit de gestandaardiseerde env-loader.

- `pepperstone_models.py`
  Kleine datamodellen voor request/response, los van de broker transportcode.

- `pepperstone_mapper.py`
  Zet `order_intent` om naar een broker-neutrale request blueprint en daarna naar een Pepperstone-specifieke order request.

- `pepperstone_transport.py`
  Bevat de transport-interface en later de echte HTTP-implementatie.

- `pepperstone_client.py`
  Dunne clientlaag die config, mapper en transport samenbrengt.

- `pepperstone_adapter.py`
  Adapter die vanaf `future_execution` of een latere execution-runner wordt aangeroepen.

## Verantwoordelijkheden

`future_execution.py`

- Blijft eigenaar van de disabled execution scaffold
- Mag alleen readiness en contractinformatie exposen
- Mag geen netwerklogica bevatten

`pepperstone_config.py`

- Roept de bestaande env-loader aan
- Valideert presence van vereiste Pepperstone vars
- Retourneert alleen veilige config metadata aan de buitenkant

`pepperstone_mapper.py`

- Leest `order_intent`
- Bepaalt order side, instrument, account-target en order placeholders
- Doet geen IO

`pepperstone_transport.py`

- Definieert het transportcontract
- Verbergt HTTP-details achter een stabiele interface
- Laat later mockbaar testen toe

`pepperstone_client.py`

- Combineert config + mapper + transport
- Is de enige plek waar later broker requests worden opgebouwd en verstuurd

## Interface-contracten

Voorgestelde shape voor config:

```python
class PepperstoneConfig(TypedDict):
    environment: str
    account_id: str
    api_key: str
    api_secret: str
    api_base_url: str | None
    configured: bool
```

Voorgestelde shape voor een broker request:

```python
class PepperstoneOrderRequest(TypedDict):
    account_id: str
    instrument: str
    side: str
    order_type: str
    size_units: str | int | float
    time_in_force: str
    stop_loss_price: float | None
    take_profit_price: float | None
    client_order_id: str | None
```

Voorgestelde shape voor een broker response:

```python
class PepperstoneOrderResponse(TypedDict):
    ok: bool
    status: str
    provider: str
    provider_order_id: str | None
    provider_raw_status: str | None
    error_code: str | None
    error_message: str | None
```

Transport-interface:

```python
class PepperstoneTransport(Protocol):
    def submit_order(self, request: PepperstoneOrderRequest) -> PepperstoneOrderResponse:
        ...
```

Client-interface:

```python
class PepperstoneClient(Protocol):
    def prepare_order(self, order_intent: dict) -> PepperstoneOrderRequest:
        ...

    def submit_prepared_order(self, request: PepperstoneOrderRequest) -> PepperstoneOrderResponse:
        ...
```

## Aanbevolen flow

1. `future_execution` levert een `order_intent`
2. `pepperstone_adapter` leest runtime-config en safety gates
3. `pepperstone_mapper` zet `order_intent` om naar `PepperstoneOrderRequest`
4. `pepperstone_client` vraagt `pepperstone_transport` om de request uit te voeren
5. Response wordt genormaliseerd naar `PepperstoneOrderResponse`

## Safety gates

Deze gates moeten voorrang houden:

- Als primary decision `WAIT` of `NO-GO` is, geen adapter-call
- Als `live_execution` niet expliciet enabled is, geen transport-call
- Als `paper_only` true is, geen live broker-call
- Als Pepperstone env onvolledig is, alleen `missing_env` status teruggeven
- Als mapping onvolledig is, alleen `invalid_order_request` teruggeven

## Foutmodel

Gebruik een klein, stabiel foutmodel:

- `missing_env`
- `invalid_order_request`
- `transport_not_initialized`
- `provider_auth_error`
- `provider_request_error`
- `provider_response_invalid`

De clientlaag moet provider-specifieke fouten intern mogen loggen, maar naar boven altijd een genormaliseerde foutstatus teruggeven.

## Eerste implementatiestap na dit ontwerp

De kleinste logische implementatie hierna is:

1. `pepperstone_models.py`
2. `pepperstone_config.py`
3. `pepperstone_mapper.py`
4. `pepperstone_transport.py` met alleen een `NullPepperstoneTransport`
5. `pepperstone_client.py` die nog steeds geen echte netwerkcall doet

Dat houdt de stap klein en maakt de transportlaag direct unit-testbaar.
