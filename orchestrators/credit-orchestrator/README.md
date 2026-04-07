# credit-orchestrator

`credit-orchestrator` is the customer-facing credit flow layer.

## Design role

- reads balance from OutSystems
- starts Stripe PaymentIntents through `stripe-wrapper`
- confirms top-ups and records internal ledger entries
- exposes transaction history

## Current routes

- `GET /credits/balance`
- `POST /credits/topup/initiate`
- `POST /credits/topup/confirm`
- `POST /credits/topup/webhook`
- `GET /credits/transactions`

## Runtime notes

- stateless service, no owned database
- depends on OutSystems, `stripe-wrapper`, and `credit-transaction-service`

## Local verification

```powershell
python -m pytest -p no:cacheprovider orchestrators/credit-orchestrator/tests
```

Related docs:

- [../README.md](../README.md)
- [../../OUTSYSTEMS.md](../../OUTSYSTEMS.md)
