# marketplace-service

`marketplace-service` stores the raw resale listing record.

## Design role

- owns listing lifecycle such as `active`, `completed`, and `cancelled`
- stores listing metadata only
- does not enrich listings with event or seller display data; `marketplace-orchestrator` does that

## Current routes

- `GET /health`
- `POST /listings`
- `GET /listings`
- `GET /listings/{listingId}`
- `PATCH /listings/{listingId}`

## Runtime notes

- dedicated PostgreSQL database
- used by both resale browse and transfer initiation flows

## Local verification

```powershell
python -m pytest -p no:cacheprovider services/marketplace-service/tests
```

Related docs:

- [../README.md](../README.md)
- [../../API.md](../../API.md)
