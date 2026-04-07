# event-service

`event-service` owns the event catalog and admin event lifecycle.

## Design role

- stores event metadata
- supports public listing and detail reads
- supports admin create, update, duplicate, publish, cancel, and delete operations
- does not aggregate venue or seat availability itself; `event-orchestrator` does that

## Current routes

- `GET /health`
- `GET /events`
- `GET /events/upcoming`
- `GET /events/search`
- `GET /events/types`
- `GET /events/{eventId}`
- `POST /events`
- `POST /admin/events/{eventId}/publish`
- `POST /admin/events/{eventId}/duplicate`
- `PUT /admin/events/{eventId}`
- `DELETE /admin/events/{eventId}`
- `POST /admin/events/{eventId}/cancel`
- `GET /admin/events`

## Runtime notes

- dedicated PostgreSQL database
- seeded through the Kubernetes `seed-events` job
- admin event creation through Kong ultimately lands here after `event-orchestrator` validates the workflow

## Local verification

```powershell
python -m pytest -p no:cacheprovider services/event-service/tests
```

Related docs:

- [../README.md](../README.md)
- [../../API.md](../../API.md)
