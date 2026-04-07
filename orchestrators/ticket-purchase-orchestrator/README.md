# ticket-purchase-orchestrator

`ticket-purchase-orchestrator` coordinates seat holds and purchase confirmation.

## Design role

- places and releases holds through gRPC calls to `seat-inventory-service`
- validates hold state with Redis cache fallback
- checks OutSystems balance before purchase completion
- creates ticket records and ledger entries
- publishes hold-expiry messages to RabbitMQ

## Current routes

- `POST /purchase/hold/{inventoryId}`
- `DELETE /purchase/hold/{inventoryId}`
- `POST /purchase/confirm/{inventoryId}`

## Runtime notes

- stateless service, no owned database
- depends on `seat-inventory-service`, Redis, RabbitMQ, `event-service`, `ticket-service`, `credit-transaction-service`, and OutSystems

## Local verification

```powershell
python -m pytest -p no:cacheprovider orchestrators/ticket-purchase-orchestrator/tests
```

Related docs:

- [../README.md](../README.md)
- [../../API.md](../../API.md)
