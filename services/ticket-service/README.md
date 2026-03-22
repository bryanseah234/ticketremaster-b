# ticket-service

Ticket Service stores ticket ownership, ticket lifecycle status, and QR metadata.

## Endpoints

- `GET /health`
- `POST /tickets`
- `GET /tickets/<ticket_id>`
- `GET /tickets/owner/<owner_id>`
- `GET /tickets/qr/<qr_hash>`
- `PATCH /tickets/<ticket_id>`

## Data Notes

- Backed by dedicated PostgreSQL schema.
- Includes fields used by QR workflows (`qrHash`, `qrTimestamp`) and ownership transfer.

## Common Local Commands

```powershell
docker compose run --rm ticket-service python -m flask --app app.py db upgrade -d migrations
docker compose up -d --build ticket-service
```

## Testing

```powershell
docker compose run --rm ticket-service python -m pytest -p no:cacheprovider tests
```

End-to-end references:
- [../../postman/README.md](../../postman/README.md)
- [../../TESTING.md](../../TESTING.md)

## Related Docs

- Services index: [../README.md](../README.md)
- Root docs hub: [../../README.md](../../README.md)

