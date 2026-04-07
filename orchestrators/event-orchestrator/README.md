# event-orchestrator

`event-orchestrator` is the public browse and admin event aggregation layer.

## Design role

- enriches events with venue and seat availability data
- exposes the seat map and seat detail views used by the frontend
- provides admin-only event creation and dashboard aggregation

## Current routes

- `GET /venues`
- `GET /events`
- `GET /events/{eventId}`
- `GET /events/{eventId}/seats`
- `GET /events/{eventId}/seats/{inventoryId}`
- `GET /admin/events/{eventId}/dashboard`
- `POST /admin/events`

## Runtime notes

- stateless service, no owned database
- depends on `event-service`, `venue-service`, `seat-service`, `seat-inventory-service`, `ticket-service`, and `user-service`

## Local verification

```powershell
python -m pytest -p no:cacheprovider orchestrators/event-orchestrator/tests
```

Related docs:

- [../README.md](../README.md)
- [../../FRONTEND.md](../../FRONTEND.md)
