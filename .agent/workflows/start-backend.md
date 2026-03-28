---
description: how to start the ticketremaster-b backend stack with all migrations and seed data
---

// turbo-all

## Steps

1. Navigate to the backend repo root:
   ```
   cd /Users/username/Documents/GitHub/ticketremaster-b
   ```

2. **Normal start** (keeps existing DB volumes):
   ```
   bash scripts/start_and_seed.sh
   ```

   **OR — Fresh start** (wipes all DB data and starts clean):
   ```
   bash scripts/start_and_seed.sh --fresh
   ```

   This script will:
   - Build and start all Docker containers
   - Run DB migrations for **all 10 services** (user, venue, seat, event, seat-inventory, ticket, ticket-log, marketplace, transfer, credit-transaction)
   - Restart each service so it reconnects to the freshly migrated schema
   - Seed baseline data (users, venues, seats, events, inventory)
   - Populate 10 events + full seat inventory via `populate_all_events.py`

3. Verify the stack is healthy:
   ```
   curl http://localhost:8000/events -H "apikey: tk_front_123456789"
   curl http://localhost:8000/marketplace -H "apikey: tk_front_123456789"
   ```

4. Kong API Gateway is available at `http://localhost:8000`
   RabbitMQ management UI is at `http://localhost:15672` (guest/guest)