# event-service

Event Service stores event metadata and exposes list, lookup, and create endpoints.

## Endpoints

- `GET /health`
- `GET /events`
- `GET /events/<event_id>`
- `POST /events`

## Data and Seeding

- Uses its own PostgreSQL schema/database.
- Seed script: `seed.py`
- Seed purpose: create baseline events for shared manual/Postman testing.

## Common Local Commands

```powershell
docker compose run --rm event-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm event-service python seed.py
docker compose up -d --build event-service
```

## Testing

- Service tests:

```powershell
docker compose run --rm event-service python -m pytest -p no:cacheprovider tests
```

- Integrated flow:
  - [../../postman/README.md](../../postman/README.md)
  - [../../TESTING.md](../../TESTING.md)

## Related Docs

- Services index: [../README.md](../README.md)
- Root docs hub: [../../README.md](../../README.md)

