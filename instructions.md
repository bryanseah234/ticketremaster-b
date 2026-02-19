# TicketRemaster — Backend Architecture Reference
>
> IS213 Enterprise Solution Development · v4.0

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
11. [Authentication & Authorization](#11-authentication--authorization)
12. [Concurrency Handling](#12-concurrency-handling)
13. [Logging & Observability](#13-logging--observability)
14. [Database Migration & Seeding Strategy](#14-database-migration--seeding-strategy)

---

## 1. System Overview

### Architecture Pattern

TicketRemaster follows a **microservices architecture** with an **Orchestrator (Saga Manager)** pattern. All external traffic flows through Kong API Gateway into the Orchestrator, which coordinates atomic services. Services communicate via gRPC (performance), REST (standard), and AMQP (async/resilience). Each service owns a dedicated PostgreSQL database — no cross-DB joins.

### Architecture Layers

| Layer | Component | Role |
|---|---|---|
| Client | Vue Web App / OutSystems | Customer UI / Staff QR scanner |
| Gateway | Kong API Gateway | Auth, rate-limiting, CORS, routing to Orchestrator |
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
| REST / HTTP | Event Svc → Inventory Svc | **Choreography exception:** Event Service calls Inventory Service directly to fetch per-seat availability when serving `GET /events/{event_id}`. This avoids routing a read-only fan-out through the Orchestrator. |
| AMQP | Orchestrator → RabbitMQ → Inventory | Async DLX-based seat auto-release. Decouples TTL recovery from the main request path. |
| REST | User Svc → SMU Notification API | 2FA OTP send and verify for critical handshakes (purchase risk check, P2P transfer). |
| REST | User Svc → Stripe API | Credit top-up. Stripe webhook confirms payment before credits are added. |

---

## 2. Folder & Repository Structure

> **Note:** The `ticketremaster-b` repository IS the backend root. All paths below are relative to the repository root.

One backend repository. Each top-level folder is a microservice with its own Dockerfile. All services are orchestrated from the root `docker-compose.yml`.

```
ticketremaster-b/
├── docker-compose.yml              # spins up everything
├── docker-compose.dev.yml          # hot-reload dev overrides
├── .env.example
├── API.md                          # full endpoint reference
├── CONTRIBUTING.md                 # team conventions
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
│   ├── init.sql                    # DB schema + seed data
│   ├── src/
│   │   ├── proto/inventory.proto
│   │   ├── models/seat.py          # AVAILABLE | HELD | SOLD | CHECKED_IN
│   │   ├── models/entry_log.py
│   │   ├── consumers/
│   │   │   └── seat_release_consumer.py
│   │   └── services/
│   │       ├── lock_service.py
│   │       ├── ownership_service.py
│   │       └── verification_service.py
│   └── Dockerfile
│
├── user-service/                   # REST
│   ├── init.sql
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
│   ├── init.sql
│   ├── src/
│   │   ├── models/order.py
│   │   ├── models/transfer.py
│   │   └── services/
│   │       ├── order_service.py
│   │       └── transfer_service.py # dispute / undo
│   └── Dockerfile
│
├── event-service/                  # REST
│   ├── init.sql
│   ├── src/
│   │   ├── models/venue.py
│   │   ├── models/event.py
│   │   └── services/event_service.py
│   └── Dockerfile
│
├── outsystems/                     # OutSystems Gatekeeper App integration
│   ├── README.md                   # Import guide for OutSystems team
│   └── verification-api-swagger.json  # Swagger 2.0 spec (importable)
│
├── rabbitmq/
│   ├── definitions.json            # DLX queues, TTL config
│   └── rabbitmq.conf
│
└── .github/
    └── workflows/
        └── ci.yml                  # lint + test on PR
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
| qr_code_hash | TEXT nullable | Latest generated encrypted QR payload (for audit). Validation is done cryptographically on the live QR, not by DB comparison. |
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
| verification_sid | TEXT nullable | SMU API `VerificationSid` for high-risk purchase OTP. Stored after `POST /SendOTP`, used in `POST /VerifyOTP`. Cleared once verified. |
| created_at | TIMESTAMP | |
| confirmed_at | TIMESTAMP | Null until payment confirmed |

**transfers**

| Column | Type | Notes |
|---|---|---|
| transfer_id | UUID PK | |
| seat_id | UUID | |
| seller_user_id | UUID | User A |
| buyer_user_id | UUID | User B |
| initiated_by | ENUM | `SELLER` \| `BUYER` — records who started the transfer |
| status | ENUM | `INITIATED` \| `PENDING_OTP` \| `COMPLETED` \| `DISPUTED` \| `REVERSED` |
| seller_otp_verified | BOOLEAN | SMU API verification for User A |
| buyer_otp_verified | BOOLEAN | SMU API verification for User B |
| seller_verification_sid | TEXT nullable | SMU API `VerificationSid` for the seller's OTP. Stored after `POST /SendOTP` for seller, used in `POST /VerifyOTP`. Cleared once verified. |
| buyer_verification_sid | TEXT nullable | SMU API `VerificationSid` for the buyer's OTP. Stored after `POST /SendOTP` for buyer, used in `POST /VerifyOTP`. Cleared once verified. |
| credits_amount | NUMERIC(10,2) | Credits transferred from B to A |
| dispute_reason | TEXT nullable | Filled on fraud flag / user dispute |
| created_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |

> **Concurrency constraint:** A UNIQUE partial index on `(seat_id) WHERE status IN ('INITIATED', 'PENDING_OTP')` prevents multiple simultaneous transfers for the same seat.

---

### events_db (Event Service)

**venues**

| Column | Type | Notes |
|---|---|---|
| venue_id | UUID PK | Primary identifier |
| name | VARCHAR(255) | e.g. Singapore Indoor Stadium |
| address | TEXT | Full address |
| total_halls | INT | Number of halls in venue |
| created_at | TIMESTAMP | |

**events**

| Column | Type | Notes |
|---|---|---|
| event_id | UUID PK | |
| name | VARCHAR(255) | e.g. Taylor Swift Eras Tour SG |
| venue_id | UUID FK | References venues.venue_id |
| hall_id | VARCHAR(20) | Specific hall — used in Scenario 3 mismatch check |
| event_date | TIMESTAMP | |
| total_seats | INT | |
| pricing_tiers | JSONB | e.g. `{"CAT1": 350, "CAT2": 200}` |

---

## 4. Docker Compose Setup

Run `docker compose up --build` from the repository root to start all services. All environment variables are loaded from `.env` (copy from `.env.example`).

```yaml
services:

  # ── Databases ──────────────────────────────────────────────
  seats-db:
    image: postgres:16
    environment:
      POSTGRES_DB: seats_db
      POSTGRES_USER: inventory_user
      POSTGRES_PASSWORD: ${INVENTORY_DB_PASS}
    volumes:
      - seats_data:/var/lib/postgresql/data
      - ./inventory-service/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U inventory_user -d seats_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  users-db:
    image: postgres:16
    environment:
      POSTGRES_DB: users_db
      POSTGRES_USER: user_svc_user
      POSTGRES_PASSWORD: ${USER_DB_PASS}
    volumes:
      - users_data:/var/lib/postgresql/data
      - ./user-service/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user_svc_user -d users_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  orders-db:
    image: postgres:16
    environment:
      POSTGRES_DB: orders_db
      POSTGRES_USER: order_svc_user
      POSTGRES_PASSWORD: ${ORDER_DB_PASS}
    volumes:
      - orders_data:/var/lib/postgresql/data
      - ./order-service/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U order_svc_user -d orders_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  events-db:
    image: postgres:16
    environment:
      POSTGRES_DB: events_db
      POSTGRES_USER: event_svc_user
      POSTGRES_PASSWORD: ${EVENT_DB_PASS}
    volumes:
      - events_data:/var/lib/postgresql/data
      - ./event-service/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U event_svc_user -d events_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── Messaging ──────────────────────────────────────────────
  rabbitmq:
    image: rabbitmq:3-management
    ports: ["5672:5672", "15672:15672"]
    volumes:
      - ./rabbitmq/definitions.json:/etc/rabbitmq/definitions.json
      - ./rabbitmq/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 15s
      timeout: 10s
      retries: 5

  # ── Microservices ───────────────────────────────────────────
  inventory-service:
    build: ./inventory-service
    depends_on:
      seats-db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    environment:
      DB_HOST: seats-db
      DB_NAME: seats_db
      DB_USER: inventory_user
      DB_PASS: ${INVENTORY_DB_PASS}
      RABBITMQ_HOST: rabbitmq
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 15s
      timeout: 5s
      retries: 3

  user-service:
    build: ./user-service
    depends_on:
      users-db:
        condition: service_healthy
    environment:
      DB_HOST: users-db
      DB_NAME: users_db
      DB_USER: user_svc_user
      DB_PASS: ${USER_DB_PASS}
      STRIPE_KEY: ${STRIPE_SECRET_KEY}
      STRIPE_WEBHOOK_SECRET: ${STRIPE_WEBHOOK_SECRET}
      SMU_API_URL: ${SMU_API_URL}
      SMU_API_KEY: ${SMU_API_KEY}
      JWT_SECRET: ${JWT_SECRET}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 15s
      timeout: 5s
      retries: 3

  order-service:
    build: ./order-service
    depends_on:
      orders-db:
        condition: service_healthy
    environment:
      DB_HOST: orders-db
      DB_NAME: orders_db
      DB_USER: order_svc_user
      DB_PASS: ${ORDER_DB_PASS}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/health"]
      interval: 15s
      timeout: 5s
      retries: 3

  event-service:
    build: ./event-service
    depends_on:
      events-db:
        condition: service_healthy
    environment:
      DB_HOST: events-db
      DB_NAME: events_db
      DB_USER: event_svc_user
      DB_PASS: ${EVENT_DB_PASS}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5002/health"]
      interval: 15s
      timeout: 5s
      retries: 3

  orchestrator-service:
    build: ./orchestrator-service
    depends_on:
      inventory-service:
        condition: service_healthy
      user-service:
        condition: service_healthy
      order-service:
        condition: service_healthy
      event-service:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    environment:
      INVENTORY_SERVICE_URL: inventory-service:50051
      USER_SERVICE_URL: http://user-service:5000
      ORDER_SERVICE_URL: http://order-service:5001
      EVENT_SERVICE_URL: http://event-service:5002
      RABBITMQ_HOST: rabbitmq
      JWT_SECRET: ${JWT_SECRET}
      QR_ENCRYPTION_KEY: ${QR_ENCRYPTION_KEY}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5003/health"]
      interval: 15s
      timeout: 5s
      retries: 3

  api-gateway:
    image: kong:3.6
    depends_on:
      orchestrator-service:
        condition: service_healthy
    ports: ["8000:8000", "8001:8001"]
    volumes:
      - ./api-gateway/kong.yml:/etc/kong/kong.yml
    environment:
      KONG_DECLARATIVE_CONFIG: /etc/kong/kong.yml
      KONG_DATABASE: "off"

volumes:
  seats_data:
  users_data:
  orders_data:
  events_data:
```

### docker-compose.dev.yml

The dev override file enables **hot-reload** during development by mounting source code as volumes and enabling debug mode. Use it alongside the main compose file:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

```yaml
# docker-compose.dev.yml — development overrides
services:
  orchestrator-service:
    volumes:
      - ./orchestrator-service/src:/app/src
    environment:
      FLASK_DEBUG: "1"
      FLASK_ENV: development

  user-service:
    volumes:
      - ./user-service/src:/app/src
    environment:
      FLASK_DEBUG: "1"
      FLASK_ENV: development

  order-service:
    volumes:
      - ./order-service/src:/app/src
    environment:
      FLASK_DEBUG: "1"
      FLASK_ENV: development

  event-service:
    volumes:
      - ./event-service/src:/app/src
    environment:
      FLASK_DEBUG: "1"
      FLASK_ENV: development

  inventory-service:
    volumes:
      - ./inventory-service/src:/app/src
```

**What it changes:**

- **Volume mounts:** Source code directories are mounted into containers, so code changes are reflected immediately without rebuilding the image.
- **Debug mode:** Flask runs in debug mode with auto-reloader enabled.
- **No image rebuild needed:** Edit your Python files locally and the Flask dev server auto-restarts.

---

## 5. Scenario 1 — Complete Ticket Purchase Flow

> Demonstrates: **pessimistic locking**, **distributed transactions**, **async recovery via RabbitMQ DLX**

### Happy Path — Success

| Step | From → To | Action |
|---|---|---|
| 1 | Client → Orchestrator | `POST /api/reserve {seat_id, user_id}` |
| 2 | Orchestrator → Inventory | gRPC `ReserveSeat(seat_id, user_id)` — runs `SELECT FOR UPDATE NOWAIT`. Seat status → `HELD`, `held_until = NOW + 5min` |
| 3 | Orchestrator → RabbitMQ | Publish TTL message to `seat.hold.queue` with 5min expiry |
| 4 | Orchestrator → Client | `200 OK` — seat locked, `order_id` returned |
| 5 | Client → Orchestrator | `POST /api/pay {order_id}` |
| 6 | Orchestrator → User Svc | `POST /credits/deduct {user_id, amount}` — checks `credit_balance >= amount` |
| 7 | Orchestrator → Order Svc | `POST /orders` — order record created with status `CONFIRMED` |
| 8 | Orchestrator → Inventory | gRPC `ConfirmSeat(seat_id, user_id)` — status → `SOLD`, `owner_user_id` set. QR code generated (see Section 7.1). |
| 9 | Orchestrator → Client | Booking confirmed — `order_id`, QR payload returned |

### Abandonment Path — TTL Expiry

| Step | Action |
|---|---|
| 1–4 | Same as Happy Path. Seat is `HELD`. |
| 5 | TTL expires — RabbitMQ DLX routes message to `seat.release.queue` |
| 6 | RabbitMQ → Inventory: consumer calls `ReleaseSeat(seat_id)` — status → `AVAILABLE`, `held_by_user_id` cleared |
| 7 | Pending order status updated to `FAILED` |

### High-Risk User Path — Mandatory OTP

If `user.is_flagged = true`, the Orchestrator intercepts after step 2 and triggers 2FA before proceeding.

| Step | Action |
|---|---|
| 2a | Orchestrator → User Svc: `GET /users/{user_id}/risk` — returns `is_flagged` |
| 2b | User Svc → SMU API: `POST /sendOTP {phone}` — OTP sent to user |
| 2c | Client → Orchestrator: `POST /api/verify-otp {otp_code}` |
| 2d | User Svc → SMU API: `POST /verifyOTP {otp_code}` — verified |
| 3 | Continue to RabbitMQ TTL publish and normal pay flow |

### Compensation Matrix — Purchase Flow

When a multi-step operation partially fails, the Orchestrator executes compensating actions in reverse order:

| Failure Point | What Already Succeeded | Compensating Actions |
|---|---|---|
| `ReserveSeat` gRPC fails (`NOWAIT` lock) | Nothing | Return `SEAT_UNAVAILABLE` to client. Client re-picks seat. No compensation needed. |
| RabbitMQ TTL publish fails | Seat is `HELD` | Call `ReleaseSeat` gRPC to release seat → `AVAILABLE`. Return error to client. |
| Credit deduction fails (insufficient balance) | Seat `HELD`, TTL published | Return `INSUFFICIENT_CREDITS`. Seat remains held — DLX will auto-release on TTL expiry. |
| Order creation fails | Credits deducted | 1. Refund credits → `POST /credits/refund {user_id, amount}`. 2. Seat remains held — DLX will auto-release. 3. Return `INTERNAL_ERROR`. |
| `ConfirmSeat` gRPC fails | Credits deducted, Order created | 1. Refund credits → `POST /credits/refund {user_id, amount}`. 2. Update order status → `FAILED`. 3. Seat remains held — DLX will auto-release. 4. Return `INTERNAL_ERROR`. |
| OTP verification fails (high-risk user) | Seat `HELD` | Keep seat held — user can retry OTP. After 3 failures: cancel flow, DLX auto-releases seat. |

---

## 6. Scenario 2 — Secure P2P Ticket Transfer

Either the seller (current ticket owner) or the buyer can initiate a transfer. Both parties must verify via SMU 2FA. Credits transfer from buyer to seller atomically.

### Success Path

| Step | From → To | Action |
|---|---|---|
| 1 | Initiator → Orchestrator | `POST /api/transfer/initiate {seat_id, seller_user_id, buyer_user_id, credits_amount}` |
| 2 | Orchestrator validation | Verify: seller owns seat (`GetSeatOwner`), buyer has credits, no pending transfer for seat (partial unique index check), seat status == `SOLD` |
| 3 | Orchestrator → Order Svc | Create transfer record — status: `INITIATED`, `initiated_by` recorded |
| 4 | Orchestrator → User Svc | Trigger OTP for both seller and buyer via SMU API `POST /sendOTP` |
| 5 | — | Transfer status → `PENDING_OTP`. Both users receive OTP. |
| 6 | Client → Orchestrator | `POST /api/transfer/confirm {transfer_id, seller_otp, buyer_otp}` |
| 7 | Orchestrator → User Svc | Verify both OTPs via SMU API `POST /verifyOTP` — both must pass |
| 8 | Atomic Swap | User Svc: credit transfer (buyer → seller). Inventory gRPC: `UpdateOwner(seat_id, buyer_id)`. Order Svc: transfer status → `COMPLETED`. |
| 9 | Orchestrator → Inventory | Generate new QR code for the new owner (see Section 7.1). Old owner's QRs become invalid (user_id mismatch). |
| 10 | Result | Seller sees ticket under Sold Tickets. Buyer sees ticket under Purchased Tickets. |

### Failure Cases

| Case | Status | Handling |
|---|---|---|
| OTP mismatch / expired | `PENDING_OTP` | User can retry. After 3 failures, transfer auto-cancels → `FAILED` |
| Buyer insufficient credits | `FAILED` | Checked before OTP is sent. User redirected to Stripe top-up |
| Seller no longer owns seat | `FAILED` | Inventory gRPC `GetSeatOwner` check at step 2. Transfer blocked immediately |
| Seat already has pending transfer | `FAILED` | Partial unique index enforces one active transfer per seat. Second attempt rejected → `TRANSFER_IN_PROGRESS` |
| Self-transfer attempt | `FAILED` | `seller_user_id == buyer_user_id` blocked at step 2 → `SELF_TRANSFER` |
| Fraud / phishing flag | `DISPUTED` | Either party calls `POST /api/transfer/dispute {transfer_id, reason}`. Credits frozen |
| Undo / reverse transfer | `REVERSED` | `POST /api/transfer/reverse` — Inventory `UpdateOwner` back to seller. Credits returned to buyer |

### Compensation Matrix — Transfer Flow

| Failure Point | What Already Succeeded | Compensating Actions |
|---|---|---|
| Validation fails (ownership, credits, dup) | Nothing | Return error to client. No side effects. |
| Transfer record creation fails | Validation passed | Return `INTERNAL_ERROR`. No side effects. |
| OTP send fails | Transfer record created | Set transfer → `FAILED`. No side effects to undo. |
| OTP verification fails (either party) | Transfer in `PENDING_OTP` | Allow retries. After 3 failures → set transfer → `FAILED`. |
| Credit transfer fails | Both OTPs verified | Set transfer → `FAILED`. No ownership change occurred. |
| `UpdateOwner` gRPC fails | Credits transferred | 1. Reverse credit transfer (return credits to buyer, deduct from seller). 2. Set transfer → `FAILED`. |
| Transfer status update fails | Credits + ownership changed | Log critical error. Both credits and ownership already changed — system is consistent. Mark for manual audit. |

---

## 7. Scenario 3 — Ticket Verification (QR Scan)

Staff scans a QR via OutSystems Gatekeeper App. QR codes contain an encrypted payload with a **60-second valid timestamp** to prevent screenshot sharing. Every scan (pass or fail) is written to `entry_logs`.

> **OutSystems Integration:** A ready-to-import Swagger 2.0 spec and step-by-step guide are in the [`outsystems/`](outsystems/) folder. See [`outsystems/README.md`](outsystems/README.md) for import instructions.

### Verification Flow

| Step | From → To | Action |
|---|---|---|
| 1 | Staff App → Orchestrator | `POST /api/verify {qr_payload, hall_id, staff_id}` |
| 2 | Orchestrator | Decrypt QR payload using `QR_ENCRYPTION_KEY` → extract `seat_id`, `user_id`, `hall_id`, `generated_at` |
| 3 | Orchestrator | Validate QR timestamp: `NOW - generated_at <= 60 seconds`. Reject if expired. |
| 4 | Orchestrator (parallel) | Fan out to 3 services simultaneously |
| 4a | → Inventory | gRPC `VerifyTicket(seat_id)` — returns status, owner, event_id |
| 4b | → Order Svc | `GET /orders?seat_id=` — confirm `CONFIRMED` order exists |
| 4c | → Event Svc | `GET /events/{event_id}` — returns expected `hall_id` |
| 5 | Orchestrator | Run all business rule checks (see table below) |
| 6 | On SUCCESS | gRPC `MarkCheckedIn(seat_id)` — status → `CHECKED_IN`. Write `entry_log` result = `SUCCESS` |
| 7 | → Staff App | Return result + display message to OutSystems |

### Business Rule Validation

| Case | Result | System Logic |
|---|---|---|
| Valid entry | SUCCESS | `seat.status == SOLD` + no prior `CHECKED_IN` log + QR `user_id` matches `seat.owner_user_id` → mark `CHECKED_IN`, log entry |
| Already scanned | REJECT | `entry_logs` has `SUCCESS` record for this `seat_id` → alert "Already Checked In". Log `DUPLICATE` |
| Unpaid seat | REJECT | `seat.status == HELD` → alert "Incomplete Payment". Log `UNPAID` |
| Ticket not found | REJECT | `seat_id` does not exist → alert "Possible Counterfeit". Log `NOT_FOUND` |
| Wrong hall/venue | REJECT | QR `hall_id` ≠ `event.hall_id` → alert "Go to Hall X". Log `WRONG_HALL` |
| Expired QR timestamp | REJECT | QR `generated_at` older than 60 seconds → alert "Expired QR — refresh ticket". Log `EXPIRED` |

### 7.1 QR Code Specification

#### Payload Structure

The QR code contains an **encrypted JSON payload** with the following fields:

```json
{
  "seat_id": "s1s2s3s4-e5e6-f7f8-g9g0-h1h2h3h4h5h6",
  "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "hall_id": "HALL-A",
  "generated_at": "2026-02-19T18:10:45Z"
}
```

| Field | Purpose |
|---|---|
| `seat_id` | Identifies the specific seat/ticket being verified |
| `user_id` | Binds the QR to the current owner — prevents use by a different person |
| `hall_id` | Enables wrong-hall detection at scan time |
| `generated_at` | ISO 8601 timestamp to the **second** — enforces 60-second TTL |

#### Encryption — AES-256-GCM

| Parameter | Value |
|---|---|
| Algorithm | AES-256-GCM (authenticated encryption) |
| Key | `QR_ENCRYPTION_KEY` from environment (32 bytes) |
| IV / Nonce | Random 12 bytes, generated fresh for each QR |
| Output format | `base64(IV ∥ ciphertext ∥ auth_tag)` |

**Why AES-256-GCM?**

- **Confidentiality** — payload is encrypted; scanning the QR without the key reveals nothing.
- **Integrity** — the GCM authentication tag detects any tampering with the payload. If even one bit is changed, decryption fails.
- **Random IV** — every QR code is cryptographically unique, even for the same seat at the same second.

#### Anti-Fraud Measures

| Threat | Mitigation |
|---|---|
| Screenshot sharing | 60-second TTL on `generated_at`. Shared screenshots expire before they can be used. |
| QR forwarding to another person | `user_id` in payload is checked against `seat.owner_user_id`. Mismatch → rejected. |
| Payload tampering | AES-GCM authentication tag. Any modification invalidates the QR. |
| QR duplication | Random 12-byte IV means no two encryptions produce the same output. |
| Replay after transfer | On ticket transfer, a new QR is generated for the new owner. Old owner's `user_id` no longer matches, so old QR codes are immediately invalidated. |

#### QR Generation Points

| Event | Trigger | Who Generates |
|---|---|---|
| Purchase confirmation | Scenario 1, Step 8 (after `ConfirmSeat`) | Orchestrator encrypts payload, stores hash in `seats.qr_code_hash` |
| Transfer completion | Scenario 2, Step 9 (after `UpdateOwner`) | Orchestrator encrypts new payload with new `user_id` |
| Client QR refresh | `GET /api/tickets/{seat_id}/qr` | Orchestrator generates fresh payload with current `generated_at` timestamp |

#### Client QR Refresh Flow

The client app should poll `GET /api/tickets/{seat_id}/qr` every **~50 seconds** to keep the displayed QR code fresh (within the 60-second TTL window).

```
Client                         Orchestrator
  │                                │
  │─── GET /tickets/{id}/qr ─────→│
  │                                │── Verify JWT user == seat owner
  │                                │── Build payload {seat_id, user_id, hall_id, NOW()}
  │                                │── Encrypt with AES-256-GCM
  │←── {qr_payload, expires_at} ──│
  │                                │
  │── render QR code from payload  │
  │── wait 50 seconds              │
  │── repeat                       │
```

### Compensation — Verification Flow

Scenario 3 is a read-heavy flow with only one write operation (`MarkCheckedIn`). Compensation is minimal:

| Failure Point | Handling |
|---|---|
| QR decryption fails | Return `QR_INVALID`. Log for audit. No side effects. |
| Any downstream service call fails | Return `SERVICE_UNAVAILABLE`. Staff retries scan. No side effects. |
| `MarkCheckedIn` gRPC fails | Return error to staff. Staff retries scan. Seat remains `SOLD`. |
| `entry_log` write fails | Non-critical. `MarkCheckedIn` already succeeded. Log error for manual audit. |

---

## 8. RabbitMQ Configuration

RabbitMQ handles the async seat auto-release (Scenario 1 abandonment). The DLX pattern ensures held seats are always released even if the Orchestrator crashes.

### Queue Design

| Queue / Exchange | Type | Purpose |
|---|---|---|
| `seat.hold.exchange` | direct | Main exchange. Published to when a seat is `HELD` |
| `seat.hold.queue` | queue (TTL=300000ms) | Holds reservation messages. `x-message-ttl` = 5 minutes |
| `seat.release.exchange` (DLX) | direct | Dead letter exchange — receives expired messages from hold queue |
| `seat.release.queue` | queue | Consumed by Inventory Service to trigger `ReleaseSeat` |

### Message Flow

```
Orchestrator ──publish──→ seat.hold.exchange ──route──→ seat.hold.queue
                                                            │
                                                     (TTL expires)
                                                            │
                                                            ▼
                                                  seat.release.exchange (DLX)
                                                            │
                                                            ▼
                                                    seat.release.queue
                                                            │
                                                            ▼
                                              Inventory Service Consumer
                                                    ReleaseSeat()
```

### Message Payload

Published by the Orchestrator when a seat is reserved:

```json
{
  "seat_id": "s1s2s3s4-...",
  "user_id": "f47ac10b-...",
  "order_id": "o1o2o3o4-...",
  "reserved_at": "2026-02-19T18:10:00Z"
}
```

### Consumer Implementation

The Inventory Service runs a **dedicated consumer thread** that listens to `seat.release.queue`. This consumer starts alongside the gRPC server on container startup.

```python
# inventory-service/src/consumers/seat_release_consumer.py
import json
import pika

def start_consumer(db_session_factory):
    """Start the RabbitMQ consumer for seat auto-release.
    Runs in a separate thread from the gRPC server.
    """
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )
    channel = connection.channel()

    def callback(ch, method, properties, body):
        data = json.loads(body)
        seat_id = data["seat_id"]
        order_id = data.get("order_id")

        try:
            # Release the seat back to AVAILABLE
            release_seat(seat_id, db_session_factory)

            # Update the pending order to FAILED (via HTTP call to Order Service)
            if order_id:
                update_order_status(order_id, "FAILED")

            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"Auto-released seat {seat_id} after TTL expiry")

        except Exception as e:
            logger.error(f"Failed to release seat {seat_id}: {e}")
            # Negative ack — message will be redelivered
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue="seat.release.queue",
        on_message_callback=callback
    )

    logger.info("Seat release consumer started, waiting for messages...")
    channel.start_consuming()
```

**Startup pattern** in the Inventory Service main entry point:

```python
# inventory-service/src/main.py
import threading

def main():
    # Start gRPC server
    grpc_server = create_grpc_server()
    grpc_server.start()

    # Start RabbitMQ consumer in a separate thread
    consumer_thread = threading.Thread(
        target=start_consumer,
        args=(db_session_factory,),
        daemon=True
    )
    consumer_thread.start()

    grpc_server.wait_for_termination()
```

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

### SMU Lab Notification API

**Base URL:** `https://smuedu-dev.outsystemsenterprise.com/SMULab_Notification/rest/Notification`

Called exclusively from `user-service/src/services/otp_service.py`. All requests use `Content-Type: application/json`.

**Authentication:** Include the API key in an HTTP header on every request:

```
X-Contacts-Key: <SMU_API_KEY from env>
```

#### POST /SendOTP

Triggers an OTP SMS to the user's mobile number via Twilio. Returns a `VerificationSid` which **must** be stored temporarily (e.g., in-memory or Redis) and passed to `/VerifyOTP` to complete verification.

**Request:**

```json
{ "Mobile": "+6591234567" }
```

**Response:**

```json
{
  "VerificationSid": "VE1234abcd...",
  "Success": true,
  "ErrorMessage": ""
}
```

> **Note:** SMS content (OTP message template) is managed by the SMU Lab platform — the caller only provides the mobile number. You do **not** specify the OTP text; the platform generates and sends it.

#### POST /VerifyOTP

Verifies an OTP submitted by the user. Requires the `VerificationSid` returned from `/SendOTP`.

**Request:**

```json
{
  "VerificationSid": "VE1234abcd...",
  "Code": "123456"
}
```

**Response:**

```json
{
  "Success": true,
  "Status": "approved",
  "ErrorMessage": ""
}
```

| `Status` value | Meaning |
|---|---|
| `approved` | OTP is correct — proceed |
| `pending` | OTP not yet submitted / wrong code |
| `expired` | OTP TTL exceeded |

#### POST /SendSMS

Send an arbitrary SMS to a mobile number.

**Request:**

```json
{ "mobile": "+6591234567", "message": "Your ticket transfer has been initiated." }
```

**Response:**

```json
{ "status": "queued" }
```

> **Note:** SMS template content for TicketRemaster notifications (e.g., transfer alerts) is **TBD** — agree on message text with team before implementing.

#### POST /SendEmail

Send an email via SendGrid.

**Request:**

```json
{
  "emailAddress": "user@example.com",
  "emailSubject": "Your TicketRemaster booking",
  "emailBody": "<h1>Booking confirmed</h1>..."
}
```

**Response:**

```json
{ "status": "sent" }
```

> **Note:** Email templates for TicketRemaster (booking confirmation, transfer notification, etc.) are **TBD** — agree on content and HTML templates with team before implementing.

#### OTP Flow — Implementation Pattern

```python
# otp_service.py
import requests

SMU_BASE = os.environ["SMU_API_URL"]  # https://smuedu-dev.outsystemsenterprise.com/SMULab_Notification/rest/Notification

def send_otp(mobile: str) -> str:
    """Send OTP and return VerificationSid to store for later verification."""
    resp = requests.post(f"{SMU_BASE}/SendOTP", json={"Mobile": mobile})
    resp.raise_for_status()
    data = resp.json()
    if not data["Success"]:
        raise RuntimeError(f"OTP send failed: {data['ErrorMessage']}")
    return data["VerificationSid"]  # Store this! Required for VerifyOTP.

def verify_otp(verification_sid: str, code: str) -> bool:
    """Verify OTP code. Returns True on success."""
    resp = requests.post(f"{SMU_BASE}/VerifyOTP", json={"VerificationSid": verification_sid, "Code": code})
    resp.raise_for_status()
    data = resp.json()
    return data["Success"] and data["Status"] == "approved"
```

> **Storage of VerificationSid:** The `VerificationSid` must survive the round-trip between `/SendOTP` and the later `/VerifyOTP` call. Store it on the transfer/order record in the DB, or in a short-TTL Redis key keyed by `user_id`.

### Stripe API (Credit Top-Up)

Called from `user-service/src/services/credit_service.py`.

| Step | Action |
|---|---|
| 1 | User requests top-up → User Svc creates Stripe Payment Intent |
| 2 | Frontend collects card details via Stripe.js (never touches your backend) |
| 3 | Stripe sends webhook `POST /api/webhooks/stripe` to User Svc on `payment.succeeded` |
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

---

## 11. Authentication & Authorization

### Why Not Roll Your Own?

Rolling custom JWT authentication from scratch introduces security risks: token validation bugs, missing expiry checks, improper signature verification, and lack of refresh/blocklist support. Use a battle-tested library instead.

### Recommended Library: Flask-JWT-Extended

[Flask-JWT-Extended](https://flask-jwt-extended.readthedocs.io/) handles:

- **JWT creation** — access + refresh tokens with configurable expiry
- **Token validation** — `@jwt_required()` decorator on protected routes
- **Custom claims** — embed `user_id`, `role` in the token payload
- **Token refresh** — secure refresh flow without re-login
- **Token blocklisting** — for logout / token revocation

```bash
pip install flask-jwt-extended
```

### JWT Token Structure

```json
{
  "sub": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "role": "customer",
  "iat": 1708300000,
  "exp": 1708300900,
  "type": "access"
}
```

| Claim | Description |
|---|---|
| `sub` | User ID (UUID) — the subject of the token |
| `role` | `customer` or `staff` — determines API access |
| `iat` | Issued at (Unix timestamp) |
| `exp` | Expires at — 15 minutes for access, 7 days for refresh |
| `type` | `access` or `refresh` |

### Token Lifecycle

```
User                    User Service                  Kong Gateway
  │                         │                              │
  │── POST /auth/login ────→│                              │
  │                         │── validate credentials       │
  │                         │── generate access (15min)    │
  │                         │── generate refresh (7 days)  │
  │←── {access, refresh} ──│                              │
  │                         │                              │
  │── GET /api/events ─────────────────────────────────────→│
  │                         │                 validate JWT ─│
  │                         │               extract claims ─│
  │                         │       forward to Orchestrator ─│
  │←── events data ────────────────────────────────────────│
  │                         │                              │
  │── (access expires)      │                              │
  │── POST /auth/refresh ──→│                              │
  │                         │── validate refresh token     │
  │                         │── issue new access token     │
  │←── {new access} ───────│                              │
```

### Kong JWT Plugin

Kong validates JWTs at the gateway level before requests reach the Orchestrator. This offloads auth from service code.

```yaml
# kong.yml — JWT plugin configuration
plugins:
  - name: jwt
    config:
      key_claim_name: sub
      secret_is_base64: false
```

**Public routes** (no JWT required): `/api/auth/login`, `/api/auth/register`, `/api/webhooks/stripe`

### Role-Based Access

| Role | Endpoints Accessible |
|---|---|
| `customer` | Reserve, pay, transfer, view tickets, refresh QR, manage credits |
| `staff` | QR verification scan (`POST /api/verify`) via OutSystems |

### CORS Configuration

> **Note:** CORS headers are set on the **backend** (API Gateway), not the frontend. The frontend merely makes requests — the server must include the appropriate `Access-Control-Allow-*` headers.

Configure Kong's CORS plugin:

```yaml
# kong.yml — CORS plugin
plugins:
  - name: cors
    config:
      origins:
        - "http://localhost:3000"
        - "https://yourdomain.com"
      methods:
        - GET
        - POST
        - PATCH
        - DELETE
        - OPTIONS
      headers:
        - Authorization
        - Content-Type
      credentials: true
      max_age: 3600
```

---

## 12. Concurrency Handling

TicketRemaster uses a **two-phase locking strategy** — optimistic during browsing, pessimistic during checkout and payment.

### Phase 1 — Selection (Optimistic, No Locks)

Users browse events and view seat maps freely. No database locks are placed during browsing. Seat availability is displayed in near-real-time but is **not guaranteed** until checkout — another user may reserve the same seat between the time it's displayed and checked out.

### Phase 2 — Checkout / Reservation (Pessimistic Locking)

When a user clicks "Checkout" / "Reserve":

1. Orchestrator calls Inventory gRPC `ReserveSeat(seat_id, user_id)`
2. Inventory executes `SELECT FOR UPDATE NOWAIT` on the seat row
3. **Lock acquired:** seat status → `HELD`, `held_until = NOW + 5min`, `held_by_user_id` set
4. **`NOWAIT` fails** (another transaction holds the lock): immediate gRPC error
   - Orchestrator returns `SEAT_UNAVAILABLE` to client
   - Client displays "This seat is no longer available. Please select another."
   - **No compensation needed** — nothing was changed

### Phase 3 — Payment (Strict Pessimistic Locking)

Credit deduction uses a database-level transaction with row-level locking:

```sql
BEGIN;
  SELECT credit_balance FROM users WHERE user_id = $1 FOR UPDATE;
  -- Application checks: balance >= amount
  UPDATE users SET credit_balance = credit_balance - $2 WHERE user_id = $1;
COMMIT;
```

The `FOR UPDATE` lock on the user row prevents two concurrent purchases from double-spending the same credits. If the transaction fails at any point, it rolls back automatically — no partial deduction.

### Phase 4 — Completion

Once payment is confirmed:

- The reservation is converted into a permanent sale (`HELD` → `SOLD`)
- The pessimistic lock is released (transaction commits)
- The DLX TTL message is now irrelevant (seat is `SOLD`, not `HELD`)

### Transfer Concurrency

A seller **cannot** initiate two transfers for the same seat:

1. **Database enforcement:** A UNIQUE partial index prevents duplicates:

   ```sql
   CREATE UNIQUE INDEX idx_one_active_transfer_per_seat
     ON transfers (seat_id)
     WHERE status IN ('INITIATED', 'PENDING_OTP');
   ```

2. **Application check:** Before creating a transfer, the Orchestrator queries for existing active transfers on the seat.
3. **Frontend:** Disable the transfer button while a transfer is pending.
4. **Backend fallback:** If a duplicate request reaches the backend (race condition), the unique index causes a constraint violation → return `TRANSFER_IN_PROGRESS`.

---

## 13. Logging & Observability

### Structured JSON Logging

All services use Python's `logging` module with **JSON-formatted output** for machine parseability and compatibility with log aggregation tools.

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "correlation_id": getattr(record, "correlation_id", None),
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

# Usage
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger = logging.getLogger(SERVICE_NAME)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```

### Correlation IDs

Each incoming request to the Orchestrator generates a unique **correlation ID** (UUID). This ID is:

1. Generated at the API Gateway (Kong) or Orchestrator on request entry
2. Passed to all downstream service calls:
   - **REST:** `X-Correlation-ID` HTTP header
   - **gRPC:** metadata key `correlation-id`
3. Included in every log line across all services

This allows **tracing a single user request** across all services for debugging.

### Log Levels

| Level | Usage |
|---|---|
| `DEBUG` | Detailed internal state (development only, disabled in production) |
| `INFO` | Request received/sent, business events, state transitions |
| `WARNING` | Recoverable issues — retries, fallbacks, DLX auto-release |
| `ERROR` | Failed operations, unhandled exceptions, compensation actions |
| `CRITICAL` | Service health compromised, database unreachable |

### What to Log

| Event | Level | Example |
|---|---|---|
| Incoming request | INFO | `POST /api/reserve seat_id=abc corr_id=xyz` |
| Outgoing service call | INFO | `→ Inventory gRPC ReserveSeat seat_id=abc` |
| Service response | INFO | `← Inventory OK in 12ms` |
| Business event | INFO | `Seat abc HELD for user def, TTL 5min` |
| State transition | INFO | `Order o123 status: PENDING → CONFIRMED` |
| Compensation action | WARNING | `Compensating: refunding 350.00 credits to user def` |
| DLX auto-release | WARNING | `Auto-released seat abc after TTL expiry` |
| Unhandled error | ERROR | Full stack trace with correlation ID |

### Docker Log Aggregation

All services log to **stdout/stderr**. Docker captures these automatically.

```bash
# Tail logs for a specific service
docker compose logs -f orchestrator-service

# Tail all services
docker compose logs -f

# Search logs for a correlation ID
docker compose logs | grep "correlation_id.*abc123"
```

---

## 14. Database Migration & Seeding Strategy

### Strategy: Init SQL Scripts

Each service has an `init.sql` file in its root directory that:

1. Creates tables using `CREATE TABLE IF NOT EXISTS` — safe to re-run
2. Seeds test data using `INSERT ... ON CONFLICT DO NOTHING` — idempotent

### Docker Integration

PostgreSQL automatically executes `.sql` files placed in `/docker-entrypoint-initdb.d/` on **first container startup** (when the data volume is empty).

```yaml
# In docker-compose.yml — each DB mounts its service's init.sql
seats-db:
  volumes:
    - seats_data:/var/lib/postgresql/data
    - ./inventory-service/init.sql:/docker-entrypoint-initdb.d/init.sql
```

### Data Persistence Rules

| Command | Effect on Data |
|---|---|
| `docker compose down` | Containers stop. **Data persists** in named volumes. |
| `docker compose up` | Containers restart. Data is still there. `init.sql` does NOT re-run. |
| `docker compose down -v` | Containers stop. **Volumes deleted** — clean slate. |
| `docker compose up` (after `-v`) | Fresh containers. `init.sql` runs, tables created, seed data inserted. |

### Seed Data Requirements

| Database | Seed Data |
|---|---|
| events_db | 1 venue (Singapore Indoor Stadium), 1–2 events with pricing tiers |
| seats_db | 20+ seats per event across rows A–D, all status `AVAILABLE` |
| users_db | 2 test users: one normal, one with `is_flagged = true`. Both with credit balances. |
| orders_db | Empty — populated during testing |

### Example Seed (events_db)

```sql
-- event-service/init.sql
CREATE TABLE IF NOT EXISTS venues (
    venue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    address TEXT,
    total_halls INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    venue_id UUID REFERENCES venues(venue_id),
    hall_id VARCHAR(20) NOT NULL,
    event_date TIMESTAMP NOT NULL,
    total_seats INT NOT NULL,
    pricing_tiers JSONB NOT NULL
);

-- Seed data
INSERT INTO venues (venue_id, name, address, total_halls)
VALUES ('a0a0a0a0-0000-0000-0000-000000000001', 'Singapore Indoor Stadium', '2 Stadium Walk, Singapore 397691', 3)
ON CONFLICT DO NOTHING;

INSERT INTO events (event_id, name, venue_id, hall_id, event_date, total_seats, pricing_tiers)
VALUES (
    'e0e0e0e0-0000-0000-0000-000000000001',
    'Taylor Swift Eras Tour SG',
    'a0a0a0a0-0000-0000-0000-000000000001',
    'HALL-A',
    '2026-06-15 19:00:00',
    5000,
    '{"CAT1": 350, "CAT2": 200, "CAT3": 120}'
)
ON CONFLICT DO NOTHING;
```

---

## 15. Testing Strategy

### Tools

| Tool | Purpose |
|---|---|
| `pytest` | Unit and integration tests — run inside Docker containers |
| Postman | Manual API testing and shared team collection |
| `curl` | Quick ad-hoc endpoint checks |
| `k6` | Optional load testing for concurrency scenarios |

### Postman Workspace

Maintain a **shared Postman workspace** for the team so everyone can test against the same collection without duplicating curl commands.

**Setup:**

1. Create a Postman workspace named `TicketRemaster`
2. Create a collection per scenario: `Auth`, `Purchase Flow`, `Transfer Flow`, `Verification`
3. Set a collection-level variable `baseUrl = http://localhost:8000` (local) / production URL
4. Set a collection-level variable `accessToken` — update it after each `/login` call using a Postman test script:

   ```js
   // In the /auth/login request → Tests tab
   const json = pm.response.json();
   pm.collectionVariables.set("accessToken", json.data.access_token);
   ```

5. All protected requests use `Authorization: Bearer {{accessToken}}`
6. Export the collection to `postman/TicketRemaster.postman_collection.json` and commit to the repo

### Running Tests Locally

Use `docker compose run` to run tests inside the container for consistency.

```bash
# Run all tests for a specific service
docker compose run --rm user-service pytest

# Run tests with coverage report
docker compose run --rm user-service pytest --cov=src

# Run tests for all services
docker compose run --rm orchestrator-service pytest
docker compose run --rm order-service pytest
docker compose run --rm event-service pytest
docker compose run --rm inventory-service pytest
```

### Manual API Testing

```bash
# Register a new user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123", "phone": "+6591234567"}'

# Login (save the access_token for subsequent requests)
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

### End-to-End Scenarios

Refer to `TASKS.md` Phase 9 for a full checklist of scenarios to test manually or automate.

---

## 15. Development Guidelines for AI Agents

**Critical Rules for AI Coding Assistants:**

1. **Follow the Plan:** Strictly follow the sequence defined in `TASKS.md`. Do not skip phases unless explicitly instructed.
2. **No Random Artifacts:** Do **NOT** create random markdown files (e.g., `audit.md`, `plan.md`, `notes.md`) in the source code repository. Keep the repository clean.
    - If you must create documentation, use the designated artifact system or update existing files like `walkthrough.md`.
3. **Update TASKS.md:** You **MUST** update `TASKS.md` immediately after completing a task or phase. Mark items as `[x]` to maintain an accurate progress log for the user and future agents.
4. **Clean Code:** Remove debug prints and temporary comments before finishing a task.
