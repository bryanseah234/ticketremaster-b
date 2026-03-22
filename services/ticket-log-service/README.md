# ticket-log-service

Ticket Log Service stores scan/check-in history for tickets.

## Endpoints

- `GET /health`
- `POST /ticket-logs`
- `GET /ticket-logs/ticket/<ticket_id>`

## Data Notes

- Used by verification flow for duplicate-scan detection and audit history.
- Runs on dedicated PostgreSQL database.

## Common Local Commands

```powershell
docker compose run --rm ticket-log-service python -m flask --app app.py db upgrade -d migrations
docker compose up -d --build ticket-log-service
```

## Testing

```powershell
docker compose run --rm ticket-log-service python -m pytest -p no:cacheprovider tests
```

Cross-service verification flow references:
- [../../TESTING.md](../../TESTING.md)
- [../../FRONTEND.md](../../FRONTEND.md)

## Related Docs

- Services index: [../README.md](../README.md)
- Root docs hub: [../../README.md](../../README.md)

