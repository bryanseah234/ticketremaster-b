# seat-service

Seat Service stores venue seat layouts and exposes seat lists by venue.

## Endpoints

- `GET /health`
- `GET /seats/venue/<venue_id>`

## Data and Seeding

- Uses isolated PostgreSQL storage.
- Seed script: `seed.py`
- Seed generates seat rows for all configured venue capacities in `VENUE_CAPACITIES`.

## Common Local Commands

```powershell
docker compose run --rm seat-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm seat-service python seed.py
docker compose up -d --build seat-service
```

## Testing

```powershell
docker compose run --rm seat-service python -m pytest -p no:cacheprovider tests
```

E2E references:
- [../../postman/README.md](../../postman/README.md)
- [../../TESTING.md](../../TESTING.md)

## Related Docs

- Services index: [../README.md](../README.md)
- Root docs hub: [../../README.md](../../README.md)

