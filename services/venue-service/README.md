# venue-service

Venue Service stores venue metadata used by event browsing and inventory generation flows.

## Endpoints

- `GET /health`
- `GET /venues`
- `GET /venues/<venue_id>`

## Data and Seeding

- Uses its own PostgreSQL database.
- Seed script: `seed.py`
- Seed includes canonical venue IDs used by other seeded services (for example `ven_001`, `ven_002`, and additional venues).

## Common Local Commands

```powershell
docker compose run --rm venue-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm venue-service python seed.py
docker compose up -d --build venue-service
```

## Testing

```powershell
docker compose run --rm venue-service python -m pytest -p no:cacheprovider tests
```

Manual E2E path:
- [../../postman/README.md](../../postman/README.md)
- [../../TESTING.md](../../TESTING.md)

## Related Docs

- Services index: [../README.md](../README.md)
- Root docs hub: [../../README.md](../../README.md)

