# transfer-service

Transfer Service stores peer-to-peer transfer workflow state, OTP verification flags, and completion metadata.

## Endpoints

- `GET /health`
- `POST /transfers`
- `GET /transfers/<transfer_id>`
- `PATCH /transfers/<transfer_id>`

## Data Notes

- Persists buyer/seller verification progress and transfer status transitions.
- Uses dedicated PostgreSQL schema for transfer records.

## Common Local Commands

```powershell
docker compose run --rm transfer-service python -m flask --app app.py db upgrade -d migrations
docker compose up -d --build transfer-service
```

## Testing

```powershell
docker compose run --rm transfer-service python -m pytest -p no:cacheprovider tests
```

Cross-service references:
- [../../services/otp-wrapper/README.md](../../services/otp-wrapper/README.md)
- [../../TESTING.md](../../TESTING.md)

## Related Docs

- Services index: [../README.md](../README.md)
- Root docs hub: [../../README.md](../../README.md)

