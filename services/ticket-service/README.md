# ticket-service

`ticket-service` owns the canonical ticket record.

## What it stores

- owner
- event and venue linkage
- inventory linkage
- price
- ticket status such as `active`, `listed`, `used`, or `payment_failed`
- QR metadata such as `qrHash` and `qrTimestamp`

## Current routes

- `GET /health`
- `POST /tickets`
- `GET /tickets/{ticketId}`
- `GET /tickets/owner/{ownerId}`
- `GET /tickets/event/{eventId}`
- `GET /tickets/qr/{qrHash}`
- `PATCH /tickets/{ticketId}`

## Design role

- purchase completion creates ticket records here
- marketplace and transfer flows update ticket ownership or listing state here
- QR generation persists fresh hashes here before staff scan validation

## Local verification

```powershell
python -m pytest -p no:cacheprovider services/ticket-service/tests
```

Related docs:

- [../README.md](../README.md)
- [../../API.md](../../API.md)
