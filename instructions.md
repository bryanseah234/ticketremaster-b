# TicketRemaster — Backend Architecture Reference
> IS213 Enterprise Solution Development · v3.4

---

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Folder & Repository Structure](#2-folder--repository-structure)
3. [Database Schemas](#3-database-schemas)
4. [Docker Compose Setup](#4-docker-compose-setup)
5. [Scenario 1 — Complete Ticket Purchase Flow](#5-scenario-1--complete-ticket-purchase-flow)
6. [Scenario 2 — Secure P2P Ticket Transfer](#6-scenario-2--secure-p2p-ticket-transfer)
7. [Scenario 3 — Ticket Verification (QR Scan)](#7-scenario-3--ticket-verification-qr-scan)
8. [RabbitMQ Configuration](#8-rabbitmq-configuration)
9. [External APIs Reference](#9-external-apis-reference)
10. [Environment Variables](#10-environment-variables)

---

## 1. System Overview

### Architecture Pattern
TicketRemaster follows a **microservices architecture** with an **Orchestrator (Saga Manager)** pattern. All external traffic flows through Kong API Gateway into the Orchestrator, which coordinates atomic services. Services communicate via gRPC (performance), REST (standard), and AMQP (async/resilience). Each service owns a dedicated PostgreSQL database — no cross-DB joins.

### Architecture Layers

| Layer | Component | Role |
|---|---|---|
| Client | Vue Web App / OutSystems | Customer UI / Staff QR scanner |
| Gateway | Kong API Gateway | Auth, rate-limiting, routing to Orchestrator |
| Composite | Orchestrator Service | Saga Manager — coordinates all multi-step flows |
| Atomic | Inventory Service (gRPC) | Seat states, locks, entry logs — Seats DB |
| Atomic | User Service (REST) | Profiles, credits, SMU 2FA — Users DB |
| Atomic | Order Service (REST) | Transaction ledger, transfer records — Orders DB |
| Atomic | Event Service (REST) | Venues, halls, pricing — Events DB |
| Messaging | RabbitMQ | Async DLX for seat auto-release on TTL expiry |
| External | Stripe API | Credit top-up payments (called from User Svc) |
| External | SMU Notification API | 2FA OTP send/verify (called from User Svc) |

### Communication Protocols

| Protocol | Path | Why |
|---|---|---|
| gRPC / HTTP2 | Orchestrator ↔ Inventory | Performance-critical seat locking. Uses `SELECT FOR UPDATE NOWAIT` to minimise lock contention under high concurrency. |
| REST / HTTP | Orchestrator ↔ User, Order, Event | Standard request/response for business logic that is not latency-critical. |
| AMQP | Orchestrator → RabbitMQ → Inventory | Async DLX-based seat auto-release. Decouples TTL recovery from the main request path. |
| REST | User Svc → SMU Notification API | 2FA OTP send and verify for critical handshakes (purchase risk check, P2P transfer). |
| REST | User Svc → Stripe API | Credit top-up. Stripe webhook confirms payment before credits are added. |

---

## 2. Folder & Repository Structure

One backend repository. Each top-level folder is a microservice with its own Dockerfile. All services are orchestrated from the root `docker-compose.yml`.

```
backend/
├── docker-compose.yml              # spins up everything
├── docker-compose.dev.yml          # hot-reload dev overrides
├── .env.example
│
├── api-gateway/
│   ├── kong.yml                    # route definitions
│   └── Dockerfile
│
├── orchestrator-service/
│   ├── src/
│   │   ├── app.py
│   │   ├── routes/
│   │   │   ├── purchase_routes.py
│   │   │   ├── transfer_routes.py
│   │   │   └── verification_routes.py
│   │   └── orchestrators/
│   │       ├── purchase_orchestrator.py
│   │       ├── transfer_orchestrator.py
│   │       └── verification_orchestrator.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── inventory-service/              # gRPC / HTTP2
│   ├── src/
│   │   ├── proto/inventory.proto
│   │   ├── models/seat.py          # AVAILABLE | HELD | SOLD | CHECKED_IN
│   │   ├── models/entry_log.py
│   │   └── services/
│   │       ├── lock_service.py
│   │       ├── ownership_service.py
│   │       └── verification_service.py
│   └── Dockerfile
│
├── user-service/                   # REST
│   ├── src/
│   │   ├── models/user.py
│   │   └── services/
│   │       ├── auth_service.py
│   │       ├── credit_service.py   # Stripe wrapper
│   │       ├── otp_service.py      # SMU API wrapper
│   │       └── transfer_service.py # credit swap
│   └── Dockerfile
│
├── order-service/                  # REST
│   ├── src/
│   │   ├── models/order.py
│   │   ├── models/transfer.py
│   │   └── services/
│   │       ├── order_service.py
│   │       └── transfer_service.py # dispute / undo
│   └── Dockerfile
│
├── event-service/                  # REST
│   ├── src/
│   │   ├── models/event.py
│   │   └── services/event_service.py
│   └── Dockerfile
│
└── rabbitmq/
    ├── definitions.json            # DLX queues, TTL config
    └── rabbitmq.conf
```

---

## 3. Database Schemas

Each microservice owns a dedicated PostgreSQL instance. No service may directly query another service's database — all cross-service data access goes through REST or gRPC calls.

### seats_db (Inventory Service)

**seats**

| Column | Type | Notes |
|---|---|---|
| seat_id | UUID PK | Primary identifier |
| event_id | UUID | Links to events_db (ID only, no JOIN) |
| owner_user_id | UUID nullable | Current ticket owner (null = available) |
| status | ENUM | `AVAILABLE` \| `HELD` \| `SOLD` \| `CHECKED_IN` |
| held_by_user_id | UUID nullable | User currently in checkout flow |
| held_until | TIMESTAMP | TTL — 5 min from reservation. DLX triggers on expiry |
| qr_code_hash | TEXT | Encrypted QR payload. Contains 60-second valid timestamp |
| price_paid | NUMERIC(10,2) | Credits charged at time of purchase |
| row_number | VARCHAR(4) | e.g. A, B, C |
| seat_number | INT | e.g. 12 |
| created_at | TIMESTAMP | Record creation time |
| updated_at | TIMESTAMP | Last state change |

**entry_logs**

| Column | Type | Notes |
|---|---|---|
| log_id | UUID PK | |
| seat_id | UUID FK | References seats.seat_id |
| scanned_at | TIMESTAMP | Server-side scan time |
| scanned_by_staff_id | UUID | Staff user ID from OutSystems app |
| result | ENUM | `SUCCESS` \| `DUPLICATE` \| `WRONG_HALL` \| `UNPAID` \| `NOT_FOUND` \| `EXPIRED` |
| hall_id_presented | VARCHAR(20) | Hall from QR payload |
| hall_id_expected | VARCHAR(20) | Hall from event record |

---

### users_db (User Service)

| Column | Type | Notes |
|---|---|---|
| user_id | UUID PK | |
| email | VARCHAR(255) UNIQUE | |
| phone | VARCHAR(20) | Used by SMU Notification API for OTP SMS |
| password_hash | TEXT | bcrypt |
| credit_balance | NUMERIC(10,2) | Internal credit. Topped up via Stripe |
| two_fa_secret | TEXT | Stored for TOTP if applicable |
| is_flagged | BOOLEAN | High-risk flag — triggers mandatory OTP on purchase |
| created_at | TIMESTAMP | |

---

### orders_db (Order Service)

**orders** — immutable transaction ledger

| Column | Type | Notes |
|---|---|---|
| order_id | UUID PK | |
| user_id | UUID | Buyer — references users_db by ID only |
| seat_id | UUID | References seats_db by ID only |
| event_id | UUID | Denormalised for query convenience |
| status | ENUM | `PENDING` \| `CONFIRMED` \| `FAILED` \| `REFUNDED` |
| credits_charged | NUMERIC(10,2) | Amount deducted at confirmation |
| created_at | TIMESTAMP | |
| confirmed_at | TIMESTAMP | Null until payment confirmed |

**transfers**

| Column | Type | Notes |
|---|---|---|
| transfer_id | UUID PK | |
| seat_id | UUID | |
| seller_user_id | UUID | User A |
| buyer_user_id | UUID | User B |
| status | ENUM | `INITIATED` \| `PENDING_OTP` \| `COMPLETED` \| `DISPUTED` \| `REVERSED` |
| seller_otp_verified | BOOLEAN | SMU API verification for User A |
| buyer_otp_verified | BOOLEAN | SMU API verification for User B |
| credits_amount | NUMERIC(10,2) | Credits transferred from B to A |
| dispute_reason | TEXT nullable | Filled on fraud flag / user dispute |
| created_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |

---

### events_db (Event Service)

| Column | Type | Notes |
|---|---|---|
| event_id | UUID PK | |
| name | VARCHAR(255) | e.g. Taylor Swift Eras Tour SG |
| venue_id | UUID | Parent venue |
| hall_id | VARCHAR(20) | Specific hall — used in Scenario 3 mismatch check |
| event_date | TIMESTAMP | |
| total_seats | INT | |
| pricing_tiers | JSONB | e.g. `{"CAT1": 350, "CAT2": 200}` |

---

## 4. Docker Compose Setup

Run `docker compose up --build` from the `backend/` root to start all services. All environment variables are loaded from `.env` (copy from `.env.example`).

```yaml
services:

  # ── Databases ──────────────────────────────────────────────
  seats-db:
    image: postgres:16
    environment:
      POSTGRES_DB: seats_db
      POSTGRES_USER: inventory_user
      POSTGRES_PASSWORD: ${INVENTORY_DB_PASS}
    volumes: [seats_data:/var/lib/postgresql/data]

  users-db:
    image: postgres:16
    environment:
      POSTGRES_DB: users_db
      POSTGRES_USER: user_svc_user
      POSTGRES_PASSWORD: ${USER_DB_PASS}
    volumes: [users_data:/var/lib/postgresql/data]

  orders-db:
    image: postgres:16
    environment:
      POSTGRES_DB: orders_db
      POSTGRES_USER: order_svc_user
      POSTGRES_PASSWORD: ${ORDER_DB_PASS}
    volumes: [orders_data:/var/lib/postgresql/data]

  events-db:
    image: postgres:16
    environment:
      POSTGRES_DB: events_db
      POSTGRES_USER: event_svc_user
      POSTGRES_PASSWORD: ${EVENT_DB_PASS}
    volumes: [events_data:/var/lib/postgresql/data]

  # ── Messaging ──────────────────────────────────────────────
  rabbitmq:
    image: rabbitmq:3-management
    ports: ["5672:5672", "15672:15672"]
    volumes:
      - ./rabbitmq/definitions.json:/etc/rabbitmq/definitions.json

  # ── Microservices ───────────────────────────────────────────
  inventory-service:
    build: ./inventory-service
    depends_on: [seats-db, rabbitmq]
    environment: {DB_HOST: seats-db, DB_NAME: seats_db}

  user-service:
    build: ./user-service
    depends_on: [users-db]
    environment:
      DB_HOST: users-db
      STRIPE_KEY: ${STRIPE_KEY}
      SMU_API_URL: ${SMU_API_URL}

  order-service:
    build: ./order-service
    depends_on: [orders-db]
    environment: {DB_HOST: orders-db}

  event-service:
    build: ./event-service
    depends_on: [events-db]
    environment: {DB_HOST: events-db}

  orchestrator-service:
    build: ./orchestrator-service
    depends_on:
      - inventory-service
      - user-service
      - order-service
      - event-service
      - rabbitmq

  api-gateway:
    image: kong:3.6
    depends_on: [orchestrator-service]
    ports: ["8000:8000", "8001:8001"]

volumes:
  seats_data:
  users_data:
  orders_data:
  events_data:
```

---

## 5. Scenario 1 — Complete Ticket Purchase Flow

> Demonstrates: **pessimistic locking**, **distributed transactions**, **async recovery via RabbitMQ DLX**

### Happy Path — Success

| Step | From → To | Action |
|---|---|---|
| 1 | Client → Orchestrator | `POST /reserve {seat_id, user_id}` |
| 2 | Orchestrator → Inventory | gRPC `ReserveSeat(seat_id, user_id)` — runs `SELECT FOR UPDATE NOWAIT`. Seat status → `HELD`, `held_until = NOW + 5min` |
| 3 | Orchestrator → RabbitMQ | Publish TTL message to `seat.hold.queue` with 5min expiry |
| 4 | Orchestrator → Client | `200 OK` — seat locked, `order_id` returned |
| 5 | Client → Orchestrator | `POST /pay {order_id}` |
| 6 | Orchestrator → User Svc | `POST /credits/deduct {user_id, amount}` — checks `credit_balance >= amount` |
| 7 | Orchestrator → Order Svc | `POST /orders` — order record created with status `CONFIRMED` |
| 8 | Orchestrator → Inventory | gRPC `ConfirmSeat(seat_id, user_id)` — status → `SOLD`, `owner_user_id` set |
| 9 | Orchestrator → Client | Booking confirmed — `order_id`, QR hash returned |

### Abandonment Path — TTL Expiry

| Step | Action |
|---|---|
| 1–4 | Same as Happy Path. Seat is `HELD`. |
| 5 | TTL expires — RabbitMQ DLX routes message to `seat.release.queue` |
| 6 | RabbitMQ → Inventory: gRPC `ReleaseSeat(seat_id)` — status → `AVAILABLE`, `held_by_user_id` cleared |
| 7 | Pending order status updated to `FAILED` |

### High-Risk User Path — Mandatory OTP

If `user.is_flagged = true`, the Orchestrator intercepts after step 2 and triggers 2FA before proceeding.

| Step | Action |
|---|---|
| 2a | Orchestrator → User Svc: `GET /users/{user_id}/risk` — returns `is_flagged` |
| 2b | User Svc → SMU API: `POST /sendOTP {phone}` — OTP sent to user |
| 2c | Client → Orchestrator: `POST /verify-otp {otp_code}` |
| 2d | User Svc → SMU API: `POST /verifyOTP {otp_code}` — verified |
| 3 | Continue to RabbitMQ TTL publish and normal pay flow |

---

## 6. Scenario 2 — Secure P2P Ticket Transfer

User A (Seller) transfers a ticket to User B (Buyer). Both parties must verify via SMU 2FA. Credits transfer from B to A atomically.

### Success Path

| Step | From → To | Action |
|---|---|---|
| 1 | Buyer → Orchestrator | `POST /transfer/initiate {seat_id, seller_id, buyer_id, credits_amount}` |
| 2 | Orchestrator → Order Svc | Create transfer record — status: `INITIATED` |
| 3 | Orchestrator → User Svc | Trigger OTP for both seller and buyer via SMU API `POST /sendOTP` |
| 4 | — | Transfer status → `PENDING_OTP`. Both users receive OTP. |
| 5 | Client → Orchestrator | `POST /transfer/confirm {transfer_id, seller_otp, buyer_otp}` |
| 6 | Orchestrator → User Svc | Verify both OTPs via SMU API `POST /verifyOTP` — both must pass |
| 7 | Atomic Swap | User Svc: credit transfer (B → A). Inventory gRPC: `UpdateOwner(seat_id, buyer_id)`. Order Svc: transfer status → `COMPLETED` |
| 8 | Result | Seller sees ticket under Sold Tickets. Buyer sees ticket under Purchased Tickets. |

### Failure Cases

| Case | Status | Handling |
|---|---|---|
| OTP mismatch / expired | `PENDING_OTP` | User can retry. After 3 failures, transfer auto-cancels → `FAILED` |
| Buyer insufficient credits | `FAILED` | Checked before OTP is sent. User redirected to Stripe top-up |
| Seller no longer owns seat | `FAILED` | Inventory gRPC `GetSeatOwner` check at step 1. Transfer blocked immediately |
| Fraud / phishing flag | `DISPUTED` | Either party calls `POST /transfer/dispute {transfer_id, reason}`. Credits frozen |
| Undo / reverse transfer | `REVERSED` | `POST /transfer/reverse` — Inventory `UpdateOwner` back to seller. Credits returned to buyer |

---

## 7. Scenario 3 — Ticket Verification (QR Scan)

Staff scans a QR via OutSystems Gatekeeper App. QR codes contain an encrypted payload with a **60-second valid timestamp** to prevent screenshot sharing. Every scan (pass or fail) is written to `entry_logs`.

### Verification Flow

| Step | From → To | Action |
|---|---|---|
| 1 | Staff App → Orchestrator | `POST /verify {qr_payload, hall_id, staff_id}` — OutSystems decrypts QR payload first |
| 2 | Orchestrator (parallel) | Fan out to 3 services simultaneously |
| 2a | → Inventory | gRPC `VerifyTicket(seat_id)` — returns status, owner, event_id |
| 2b | → Order Svc | `GET /orders?seat_id=` — confirm `CONFIRMED` order exists |
| 2c | → Event Svc | `GET /events/{event_id}` — returns expected `hall_id` |
| 3 | Orchestrator | Run all business rule checks (see table below) |
| 4 | On SUCCESS | gRPC `MarkCheckedIn(seat_id)` — status → `CHECKED_IN`. Write `entry_log` result = `SUCCESS` |
| 5 | → Staff App | Return result + display message to OutSystems |

### Business Rule Validation

| Case | Result | System Logic |
|---|---|---|
| Valid entry | SUCCESS | `seat.status == SOLD` + no prior `CHECKED_IN` log → mark `CHECKED_IN`, log entry |
| Already scanned | REJECT | `entry_logs` has `SUCCESS` record for this `seat_id` → alert "Already Checked In". Log `DUPLICATE` |
| Unpaid seat | REJECT | `seat.status == HELD` → alert "Incomplete Payment". Log `UNPAID` |
| Ticket not found | REJECT | `seat_id` does not exist → alert "Possible Counterfeit". Log `NOT_FOUND` |
| Wrong hall/venue | REJECT | QR `hall_id` ≠ `event.hall_id` → alert "Go to Hall X". Log `WRONG_HALL` |
| Expired QR timestamp | REJECT | QR timestamp older than 60 seconds → alert "Expired QR — refresh ticket". Log `EXPIRED` |

---

## 8. RabbitMQ Configuration

RabbitMQ handles the async seat auto-release (Scenario 1 abandonment). The DLX pattern ensures held seats are always released even if the Orchestrator crashes.

### Queue Design

| Queue / Exchange | Type | Purpose |
|---|---|---|
| `seat.hold.exchange` | direct | Main exchange. Published to when a seat is `HELD` |
| `seat.hold.queue` | queue (TTL=300000ms) | Holds reservation messages. `x-message-ttl` = 5 minutes |
| `seat.release.exchange` (DLX) | direct | Dead letter exchange — receives expired messages from hold queue |
| `seat.release.queue` | queue | Consumed by Inventory Service to trigger `ReleaseSeat` gRPC |

### definitions.json

```json
{
  "exchanges": [
    {"name": "seat.hold.exchange",    "type": "direct", "durable": true},
    {"name": "seat.release.exchange", "type": "direct", "durable": true}
  ],
  "queues": [
    {
      "name": "seat.hold.queue",
      "durable": true,
      "arguments": {
        "x-message-ttl": 300000,
        "x-dead-letter-exchange": "seat.release.exchange"
      }
    },
    {"name": "seat.release.queue", "durable": true}
  ],
  "bindings": [
    {"source": "seat.hold.exchange",    "destination": "seat.hold.queue"},
    {"source": "seat.release.exchange", "destination": "seat.release.queue"}
  ]
}
```

---

## 9. External APIs Reference

### SMU Lab Notification API (2FA)

Called exclusively from `user-service/src/services/otp_service.py`. Used in Scenario 1 (high-risk user) and Scenario 2 (both-party handshake).

| Endpoint | Method | Payload | Called When |
|---|---|---|---|
| `/sendOTP` | POST | `{phone_number, message}` | Before finalising risky purchase or initiating transfer |
| `/verifyOTP` | POST | `{phone_number, otp_code}` | After user submits received OTP code |

### Stripe API (Credit Top-Up)

Called from `user-service/src/services/credit_service.py`.

| Step | Action |
|---|---|
| 1 | User requests top-up → User Svc creates Stripe Payment Intent |
| 2 | Frontend collects card details via Stripe.js (never touches your backend) |
| 3 | Stripe sends webhook `POST /webhooks/stripe` to User Svc on `payment.succeeded` |
| 4 | User Svc updates `credit_balance` in `users_db` only after webhook verified |

---

## 10. Environment Variables

Copy `.env.example` to `.env` before running.

```env
# ── Database passwords ──────────────────────────────────────────
INVENTORY_DB_PASS=change_me
USER_DB_PASS=change_me
ORDER_DB_PASS=change_me
EVENT_DB_PASS=change_me

# ── RabbitMQ ────────────────────────────────────────────────────
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASS=guest

# ── External APIs ───────────────────────────────────────────────
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
SMU_API_URL=https://smunotification.yourlaburl.com
SMU_API_KEY=your_smu_api_key

# ── Service URLs (used by Orchestrator) ─────────────────────────
INVENTORY_SERVICE_URL=inventory-service:50051    # gRPC port
USER_SERVICE_URL=http://user-service:5000
ORDER_SERVICE_URL=http://order-service:5001
EVENT_SERVICE_URL=http://event-service:5002

# ── Security ────────────────────────────────────────────────────
JWT_SECRET=your_jwt_secret_here
QR_ENCRYPTION_KEY=your_32_byte_key_here
```
