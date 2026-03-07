# Seed Data Reference — TicketRemaster

> **For development & testing only.** This file documents all seeded test data so your team and AI agents can find credentials, UUIDs, and test values quickly.

---

## Test User Credentials

| User | Email | Password | Phone | Credits | Flagged | UUID |
|------|-------|----------|-------|---------|---------|------|
| Normal user | `user1@example.com` | `password123` | `+6591234567` | $1,000 | ❌ No | `41414141-4141-4141-4141-414141414141` |
| High-risk user | `user2@example.com` | `password123` | `+6598765432` | $500 | ✅ Yes | `42424242-4242-4242-4242-424242424242` |

- **Password for both users:** `password123`
- **OTP code (mock):** `123456` (always passes in dev)

---

## Test Event & Venue

| Entity | Name | UUID |
|--------|------|------|
| Venue | Singapore Indoor Stadium | `a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1` |
| Event | Taylor Swift: The Eras Tour | `e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1` |

- **Hall:** `HALL-A`
- **Event Date:** `2026-03-02 19:00:00`
- **Pricing:** CAT1 = $350, CAT2 = $250, CAT3 = $180

---

## Test Seats (20 seats)

All seats are for event `e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1`.

| Row | Seats | UUID pattern | Status |
|-----|-------|-------------|--------|
| A | 1–5 | `55555555-5555-5555-5555-5555555551XX` (01–05) | AVAILABLE |
| B | 1–5 | `55555555-5555-5555-5555-5555555551XX` (06–10) | AVAILABLE |
| C | 1–5 | `55555555-5555-5555-5555-5555555551XX` (11–15) | AVAILABLE |
| D | 1–5 | `55555555-5555-5555-5555-5555555551XX` (16–20) | AVAILABLE |

**Example seat UUIDs:**

- Row A, Seat 1: `55555555-5555-5555-5555-555555555101`
- Row B, Seat 3: `55555555-5555-5555-5555-555555555108`
- Row D, Seat 5: `55555555-5555-5555-5555-555555555120`

---

## Service Ports (Docker)

| Service | Internal Port | External Port |
|---------|--------------|---------------|
| User Service | 5000 | `localhost:5000` |
| Order Service | 5001 | `localhost:5001` |
| Event Service | 5002 | `localhost:5002` |
| Orchestrator | 5003 | (via Kong only) |
| Inventory (gRPC) | 50051 | — |
| Inventory (health) | 8080 | — |
| Kong API Gateway | 8000 | `localhost:8000` |
| Kong Admin | 8001 | `localhost:8001` |
| RabbitMQ AMQP | 5672 | `localhost:5672` |
| RabbitMQ UI | 15672 | `localhost:15672` |

---

## Database Connections

| Database | Host (Docker) | Port (external) | User | Password | DB Name |
|----------|--------------|-----------------|------|----------|---------|
| Seats DB | `seats-db` | `localhost:5433` | `inventory_user` | `inventory_dev_pass` | `seats_db` |
| Users DB | `users-db` | `localhost:5434` | `user_svc_user` | `user_dev_pass` | `users_db` |
| Orders DB | `orders-db` | `localhost:5435` | `order_svc_user` | `order_dev_pass` | `orders_db` |
| Events DB | `events-db` | `localhost:5436` | `event_svc_user` | `event_dev_pass` | `events_db` |

---

## RabbitMQ

- **URL:** `localhost:15672` (management UI)
- **User:** `guest`
- **Password:** `guest`

---

## Quick Test Commands

```bash
# Login as normal user
curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user1@example.com","password":"password123"}'

# List events
curl -s http://localhost:5002/events

# Create an order
curl -s -X POST http://localhost:5001/orders \
  -H "Content-Type: application/json" \
  -d '{"user_id":"41414141-4141-4141-4141-414141414141","seat_id":"55555555-5555-5555-5555-555555555101","event_id":"e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1","credits_charged":150}'
```
