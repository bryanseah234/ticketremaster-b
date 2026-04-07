# venue-service

`venue-service` owns canonical venue metadata.

## Design role

- provides the read model for venue name and address data
- is intentionally separate from `event-service`
- is used by event browse, ticket QR enrichment, and staff verification responses

## Current routes

- `GET /health`
- `GET /venues`
- `GET /venues/{venueId}`

## Runtime notes

- dedicated PostgreSQL database
- seeded through the Kubernetes `seed-venues` job
- read-only for most frontend-facing flows

## Local verification

```powershell
python -m pytest -p no:cacheprovider services/venue-service/tests
```

Related docs:

- [../README.md](../README.md)
- [../../API.md](../../API.md)
