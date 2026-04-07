# seat-service

`seat-service` owns the physical seat definitions for a venue.

## Design role

- stores seat metadata such as row and seat number
- does not own event-specific availability
- works together with `seat-inventory-service`, which owns `available`, `held`, and `sold` state per event

## Current routes

- `GET /health`
- `GET /seats/venue/{venueId}`

## Runtime notes

- dedicated PostgreSQL database
- seeded through the Kubernetes `seed-seats` job
- queried by `event-orchestrator` and admin reporting flows

## Local verification

```powershell
python -m pytest -p no:cacheprovider services/seat-service/tests
```

Related docs:

- [../README.md](../README.md)
- [../../INSTRUCTION.md](../../INSTRUCTION.md)
