# seat-inventory-service

Tracks per-event seat availability and exposes both REST and gRPC operations:

- `GET /health`
- `GET /inventory/event/<event_id>`
- gRPC `HoldSeat`, `ReleaseSeat`, `SellSeat`, `GetSeatStatus`

## Local development

1. Install dependencies: `pip install -r requirements.txt`
2. Set `SEAT_INVENTORY_SERVICE_DATABASE_URL`
3. Run migrations: `flask --app app.py db upgrade -d migrations`
4. Seed sample records: `python seed.py`
5. Start both servers: `python server.py`

## Tests

- Unit tests (SQLite): `python -m pytest -p no:cacheprovider tests`
- Optional Postgres lock test: set `SEAT_INVENTORY_POSTGRES_TEST_URL` and run `python -m pytest -p no:cacheprovider tests/test_seat_inventory_postgres.py`

