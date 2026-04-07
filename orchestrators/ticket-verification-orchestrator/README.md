# ticket-verification-orchestrator

`ticket-verification-orchestrator` is the staff-only ticket entry validation layer.

## Design role

- validates QR hashes and manual ticket IDs
- enforces the exact scan-order checks used by the venue staff flow
- uses Redis-backed distributed locks to reduce concurrent double-scan races
- writes check-in outcomes to `ticket-log-service`

## Current routes

- `POST /verify/scan`
- `POST /verify/manual`

## Runtime notes

- stateless service, no owned database
- depends on `ticket-service`, `ticket-log-service`, `event-service`, `venue-service`, `seat-inventory-service`, and Redis
- staff `venueId` is read from the JWT, never from the request body

## Local verification

```powershell
python -m pytest -p no:cacheprovider orchestrators/ticket-verification-orchestrator/tests
```

Related docs:

- [../README.md](../README.md)
- [../../API.md](../../API.md)
