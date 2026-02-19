# TicketRemaster — Implementation Tasks
> Work through these in order. Each phase builds on the previous one.

---

## Phase 0 — Project Setup

- [ ] Create `backend/` repo, initialise git
- [ ] Copy folder structure from `instructions.md` Section 2 — create all empty directories
- [ ] Create `.env` from `.env.example` and fill in placeholder values
- [ ] Write a root-level `README.md` with setup instructions

---

## Phase 1 — Infrastructure (get everything running empty)

- [ ] Write `docker-compose.yml` with all 4 postgres DBs, RabbitMQ, and service stubs
- [ ] Write `rabbitmq/definitions.json` with `seat.hold.queue`, `seat.release.queue`, DLX exchange, and TTL=300000ms bindings (see `instructions.md` Section 8)
- [ ] Write `rabbitmq/rabbitmq.conf` to load definitions on startup
- [ ] Add a `Dockerfile` to each service folder (can be minimal/placeholder for now)
- [ ] Run `docker compose up --build` and confirm all containers start without errors
- [ ] Confirm RabbitMQ management UI is reachable at `localhost:15672`
- [ ] Confirm all 4 Postgres instances are reachable

---

## Phase 2 — Database Setup

- [ ] **seats_db**: Write migration/init SQL for `seats` table and `entry_logs` table (schema in `instructions.md` Section 3)
- [ ] **users_db**: Write migration/init SQL for `users` table
- [ ] **orders_db**: Write migration/init SQL for `orders` table and `transfers` table
- [ ] **events_db**: Write migration/init SQL for `events` table
- [ ] Add init SQL files to each service and load them via Docker volume mounts or an ORM migration on startup
- [ ] Seed `events_db` with at least one test event and halls
- [ ] Seed `seats_db` with test seats linked to the test event
- [ ] Seed `users_db` with at least two test users (for transfer scenario)

---

## Phase 3 — Event Service (simplest, start here)

- [ ] Scaffold Flask/FastAPI app in `event-service/src/`
- [ ] Connect to `events_db` via SQLAlchemy or psycopg2
- [ ] Implement `GET /events` — list all events
- [ ] Implement `GET /events/{event_id}` — returns event including `hall_id` and `venue_id`
- [ ] Write a `Dockerfile` and confirm service runs in Docker
- [ ] Test with curl or Postman

---

## Phase 4 — User Service

- [ ] Scaffold Flask/FastAPI app in `user-service/src/`
- [ ] Connect to `users_db`
- [ ] Implement `POST /users/register` and `POST /users/login` (JWT)
- [ ] Implement `GET /users/{user_id}` — return profile including `is_flagged`
- [ ] Implement `GET /users/{user_id}/risk` — return `{is_flagged: bool}`
- [ ] Implement `POST /credits/deduct {user_id, amount}` — subtract from `credit_balance`
- [ ] Implement `POST /credits/transfer {from_user_id, to_user_id, amount}` — atomic credit swap
- [ ] Implement `POST /otp/send {user_id}` — calls SMU API `POST /sendOTP` with user phone
- [ ] Implement `POST /otp/verify {user_id, otp_code}` — calls SMU API `POST /verifyOTP`
- [ ] Implement Stripe webhook endpoint `POST /webhooks/stripe` — add credits on `payment.succeeded`
- [ ] Write a `Dockerfile` and test all endpoints

---

## Phase 5 — Order Service

- [ ] Scaffold Flask/FastAPI app in `order-service/src/`
- [ ] Connect to `orders_db`
- [ ] Implement `POST /orders` — create order record (status: `PENDING`)
- [ ] Implement `PATCH /orders/{order_id}` — update status (`CONFIRMED`, `FAILED`, `REFUNDED`)
- [ ] Implement `GET /orders?seat_id=` — fetch order by seat (used in Scenario 3)
- [ ] Implement `POST /transfers` — create transfer record (status: `INITIATED`)
- [ ] Implement `PATCH /transfers/{transfer_id}` — update status through lifecycle
- [ ] Implement `POST /transfers/{transfer_id}/dispute` — set status `DISPUTED`, store reason
- [ ] Implement `POST /transfers/{transfer_id}/reverse` — set status `REVERSED`
- [ ] Write a `Dockerfile` and test all endpoints

---

## Phase 6 — Inventory Service (gRPC)

- [ ] Define `inventory.proto` with the following RPCs:
  - `ReserveSeat(seat_id, user_id)` → sets status `HELD`, `held_until`
  - `ConfirmSeat(seat_id, user_id)` → sets status `SOLD`, `owner_user_id`
  - `ReleaseSeat(seat_id)` → sets status `AVAILABLE`, clears held fields
  - `UpdateOwner(seat_id, new_owner_id)` → for P2P transfer
  - `VerifyTicket(seat_id)` → returns status, owner, event_id
  - `MarkCheckedIn(seat_id)` → sets status `CHECKED_IN`
- [ ] Generate gRPC stubs from `.proto`
- [ ] Implement `lock_service.py` — `ReserveSeat` using `SELECT FOR UPDATE NOWAIT`
- [ ] Implement `ownership_service.py` — `UpdateOwner`, `ConfirmSeat`
- [ ] Implement `verification_service.py` — `VerifyTicket`, `MarkCheckedIn`, write to `entry_logs`
- [ ] Add RabbitMQ consumer in `inventory-service` that listens to `seat.release.queue` and calls `ReleaseSeat`
- [ ] Write a `Dockerfile` and test gRPC calls with `grpcurl` or a test script

---

## Phase 7 — Orchestrator Service

- [ ] Scaffold Flask/FastAPI app in `orchestrator-service/src/`
- [ ] Set up gRPC client to connect to `inventory-service`
- [ ] Set up HTTP clients (requests/httpx) for User, Order, Event services
- [ ] Set up RabbitMQ publisher connection

### Scenario 1 — Purchase Flow
- [ ] Implement `POST /reserve {seat_id, user_id}` in `purchase_routes.py`
  - [ ] Call Inventory gRPC `ReserveSeat`
  - [ ] Publish TTL message to `seat.hold.queue`
  - [ ] Return `order_id` to client
- [ ] Implement `POST /pay {order_id}` in `purchase_routes.py`
  - [ ] Check `is_flagged` → if true, require OTP before proceeding
  - [ ] Call User Svc `POST /credits/deduct`
  - [ ] Call Order Svc `POST /orders` (CONFIRMED)
  - [ ] Call Inventory gRPC `ConfirmSeat`
  - [ ] Return booking confirmation

### Scenario 2 — P2P Transfer
- [ ] Implement `POST /transfer/initiate` in `transfer_routes.py`
  - [ ] Validate seller owns the seat (Inventory gRPC `VerifyTicket`)
  - [ ] Validate buyer has enough credits (User Svc)
  - [ ] Create transfer record (Order Svc)
  - [ ] Trigger OTP for both parties (User Svc)
- [ ] Implement `POST /transfer/confirm` in `transfer_routes.py`
  - [ ] Verify both OTPs (User Svc)
  - [ ] Execute atomic swap: credit transfer + `UpdateOwner`
  - [ ] Update transfer status to `COMPLETED`
- [ ] Implement `POST /transfer/dispute` — delegate to Order Svc
- [ ] Implement `POST /transfer/reverse` — reverse ownership + credits

### Scenario 3 — QR Verification
- [ ] Implement `POST /verify` in `verification_routes.py`
  - [ ] Fan out parallel calls to Inventory, Order Svc, Event Svc
  - [ ] Run all business rule checks (status, entry_logs, hall_id, QR timestamp)
  - [ ] On pass: call Inventory gRPC `MarkCheckedIn`
  - [ ] Return result code + display message

---

## Phase 8 — API Gateway (Kong)

- [ ] Write `kong.yml` with routes pointing to `orchestrator-service`
- [ ] Add rate limiting plugin config (protect against surge traffic)
- [ ] Add JWT auth plugin config
- [ ] Test that requests through `localhost:8000` correctly reach the Orchestrator

---

## Phase 9 — End-to-End Testing

### Scenario 1 — Purchase
- [ ] Test happy path: reserve → pay → confirm booking
- [ ] Test abandonment: reserve → wait for TTL → confirm seat returns to `AVAILABLE`
- [ ] Test high-risk user: reserve → OTP prompt → verify OTP → pay

### Scenario 2 — Transfer
- [ ] Test success path: initiate → both OTPs → confirm → verify ownership changed
- [ ] Test OTP failure: wrong OTP → transfer stays `PENDING_OTP`
- [ ] Test dispute: flag transfer → confirm status `DISPUTED`
- [ ] Test reverse: reverse transfer → confirm ownership and credits restored

### Scenario 3 — Verification
- [ ] Test valid scan → `CHECKED_IN`
- [ ] Test duplicate scan → `DUPLICATE` alert
- [ ] Test `HELD` seat scan → `UNPAID` alert
- [ ] Test non-existent seat → `NOT_FOUND` alert
- [ ] Test wrong hall → `WRONG_HALL` alert
- [ ] Test expired QR timestamp → `EXPIRED` alert

---

## Phase 10 — Polish

- [ ] Add proper error handling and HTTP status codes across all services
- [ ] Add request validation (Pydantic models or equivalent)
- [ ] Add basic logging to each service (request in, response out, errors)
- [ ] Write a `docker-compose.dev.yml` with volume mounts for hot reload during development
- [ ] Update root `README.md` with full setup and run instructions
- [ ] Do a full `docker compose down -v && docker compose up --build` clean run to confirm everything works from scratch
