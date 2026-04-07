# qr-orchestrator

`qr-orchestrator` serves the customer's ticket list and fresh QR generation flow.

## Design role

- lists the authenticated user's tickets
- enriches tickets with event and venue display data
- generates a fresh QR hash on demand and persists it on the ticket record

## Current routes

- `GET /tickets`
- `GET /tickets/{ticketId}/qr`

## Runtime notes

- stateless service, no owned database
- depends on `ticket-service`, `event-service`, `venue-service`, and `seat-inventory-service`
- QR TTL is currently 60 seconds

## Local verification

```powershell
python -m pytest -p no:cacheprovider orchestrators/qr-orchestrator/tests
```

Related docs:

- [../README.md](../README.md)
- [../../FRONTEND.md](../../FRONTEND.md)
