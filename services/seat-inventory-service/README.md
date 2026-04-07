# seat-inventory-service

`seat-inventory-service` owns event-specific seat state.

## Design role

- keeps the authoritative inventory record for each seat at each event
- exposes REST for inventory reads and seeding
- exposes gRPC for hold, release, sell, and status checks used by purchase flows
- writes a short-lived Redis hold cache to accelerate confirm-path validation

## Current interfaces

### REST

- `GET /health`
- `GET /inventory/event/{eventId}`
- `POST /inventory/batch`

### gRPC

- `HoldSeat`
- `ReleaseSeat`
- `SellSeat`
- `GetSeatStatus`

## Runtime notes

- dedicated PostgreSQL database
- seeded through the Kubernetes `seed-seat-inventory` job
- one of the most important dependencies for purchase and verification flows

## Local verification

```powershell
python -m pytest -p no:cacheprovider services/seat-inventory-service/tests
```

Optional Postgres-specific locking test:

```powershell
python -m pytest -p no:cacheprovider services/seat-inventory-service/tests/test_seat_inventory_postgres.py
```

Related docs:

- [../README.md](../README.md)
- [../../shared/grpc/README.md](../../shared/grpc/README.md)
