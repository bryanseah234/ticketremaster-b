# marketplace-service

Marketplace Service stores resale listings and listing state transitions.

## Endpoints

- `GET /health`
- `POST /listings`
- `GET /listings`
- `GET /listings/<listing_id>`
- `PATCH /listings/<listing_id>`

## Data Notes

- Listing state supports values such as active, completed, and cancelled.
- Backed by service-owned PostgreSQL database.

## Common Local Commands

```powershell
docker compose run --rm marketplace-service python -m flask --app app.py db upgrade -d migrations
docker compose up -d --build marketplace-service
```

## Testing

```powershell
docker compose run --rm marketplace-service python -m pytest -p no:cacheprovider tests
```

Integration references:
- [../../postman/README.md](../../postman/README.md)
- [../../TESTING.md](../../TESTING.md)

## Related Docs

- Services index: [../README.md](../README.md)
- Root docs hub: [../../README.md](../../README.md)

