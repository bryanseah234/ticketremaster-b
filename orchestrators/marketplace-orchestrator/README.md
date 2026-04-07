# marketplace-orchestrator

`marketplace-orchestrator` exposes the resale marketplace browse and listing workflow.

## Design role

- browses active listings publicly
- enriches listings with event and seller display data
- lists owned tickets for sale and delists them when needed

## Current routes

- `GET /marketplace`
- `POST /marketplace/list`
- `DELETE /marketplace/{listingId}`

## Runtime notes

- stateless service, no owned database
- depends on `marketplace-service`, `ticket-service`, `event-service`, `seat-inventory-service`, and `user-service`

## Local verification

```powershell
python -m pytest -p no:cacheprovider orchestrators/marketplace-orchestrator/tests
```

Related docs:

- [../README.md](../README.md)
- [../../API.md](../../API.md)
