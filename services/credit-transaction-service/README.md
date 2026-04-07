# credit-transaction-service

`credit-transaction-service` is the internal credit ledger.

## Design role

- records top-ups, purchases, and transfer-side credit movements
- supports idempotency and replay checks through `referenceId` lookup
- complements the OutSystems balance authority rather than replacing it

## Current routes

- `GET /health`
- `POST /credit-transactions`
- `GET /credit-transactions/user/{userId}`
- `GET /credit-transactions/reference/{referenceId}`

## Runtime notes

- dedicated PostgreSQL database
- used by `credit-orchestrator`, `ticket-purchase-orchestrator`, and `transfer-orchestrator`

## Local verification

```powershell
python -m pytest -p no:cacheprovider services/credit-transaction-service/tests
```

Related docs:

- [../README.md](../README.md)
- [../../OUTSYSTEMS.md](../../OUTSYSTEMS.md)
