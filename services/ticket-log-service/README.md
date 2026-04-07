# ticket-log-service

`ticket-log-service` stores ticket scan and verification history.

## Design role

- append-only check-in and scan status history
- powers duplicate-scan detection for staff verification
- provides an audit trail for ticket usage outcomes

## Current routes

- `GET /health`
- `POST /ticket-logs`
- `GET /ticket-logs/ticket/{ticketId}`

## Runtime notes

- dedicated PostgreSQL database
- queried by `ticket-verification-orchestrator` before marking a ticket used

## Local verification

```powershell
python -m pytest -p no:cacheprovider services/ticket-log-service/tests
```

Related docs:

- [../README.md](../README.md)
- [../../API.md](../../API.md)
