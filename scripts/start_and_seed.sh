#!/bin/bash
# TicketRemaster — Full stack startup + migration + seed
# Run from the repo root: bash scripts/start_and_seed.sh
# Pass --fresh to wipe volumes and start clean: bash scripts/start_and_seed.sh --fresh

set -e
cd "$(dirname "$0")/.."

if [[ "$1" == "--fresh" ]]; then
  echo "==> Wiping volumes and stopping existing containers..."
  docker compose down -v
fi

# ── 1. Build & start all containers ──────────────────────────────────────────
echo "==> Building and starting all containers..."
docker compose up -d --build

echo "==> Waiting for databases to become healthy..."
sleep 5

# ── 2. Migrations (all services with a DB) ───────────────────────────────────
echo "==> Running database migrations..."
SERVICES=(
  user-service
  venue-service
  seat-service
  event-service
  seat-inventory-service
  ticket-service
  ticket-log-service
  marketplace-service
  transfer-service
  credit-transaction-service
)

for svc in "${SERVICES[@]}"; do
  echo "    Migrating $svc..."
  docker compose run --rm "$svc" python -m flask --app app.py db upgrade -d migrations
done

# ── 3. Restart services so they reconnect to fresh schemas ───────────────────
echo "==> Restarting services against fresh schemas..."
docker compose restart "${SERVICES[@]}"

echo "==> Waiting for services to come back up..."
sleep 10

# ── 4. Baseline seeds ────────────────────────────────────────────────────────
echo "==> Seeding baseline data..."
SEED_SERVICES=(
  user-service
  venue-service
  seat-service
  event-service
  seat-inventory-service
)

for svc in "${SEED_SERVICES[@]}"; do
  echo "    Seeding $svc..."
  docker compose run --rm "$svc" python seed.py
done

# ── 5. Populate events + inventory ───────────────────────────────────────────
echo "==> Populating events, seats, and seat inventory..."
docker cp scripts/populate_all_events.py ticketremaster-event-service-1:/app/
docker exec ticketremaster-event-service-1 python populate_all_events.py

echo ""
echo "✅  Stack is up, migrated, and seeded!"
echo "    Kong API Gateway: http://localhost:8000"
echo "    RabbitMQ UI:      http://localhost:15672"
