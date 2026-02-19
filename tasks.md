# TicketRemaster — Implementation Tasks
>
> Work through these in order. Each phase builds on the previous one.
> Cross-reference `INSTRUCTIONS.md` for schemas, flow details, and configuration.
> Cross-reference `API.md` for request/response contracts and error codes.

---

## Phase 0 — Project Setup

- [x] Create repo, initialise git
- [x] Copy folder structure from `INSTRUCTIONS.md` Section 2 — create all empty directories
  - `api-gateway/`, `orchestrator-service/src/routes/`, `orchestrator-service/src/orchestrators/`
  - `inventory-service/src/proto/`, `inventory-service/src/models/`, `inventory-service/src/services/`, `inventory-service/src/consumers/`
  - `user-service/src/models/`, `user-service/src/services/`
  - `order-service/src/models/`, `order-service/src/services/`
  - `event-service/src/models/`, `event-service/src/services/`
  - `rabbitmq/`
- [x] Create `.env` from `.env.example` and fill in **local** placeholder values
  - Fill all `*_DB_PASS` values with dev-safe passwords
  - Set `JWT_SECRET` to any long random string
  - Set `QR_ENCRYPTION_KEY` to exactly 32 characters/bytes
  - Set `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` to Stripe test keys
  - Set `SMU_API_URL` and `SMU_API_KEY` from your lab environment
- [x] Write a root-level `README.md` with setup instructions (✅ already done — verify it stays up to date)

---

## Phase 1 — Infrastructure (get everything running empty)

- [x] Write `docker-compose.yml` with:
  - All 4 PostgreSQL DBs (`seats-db`, `users-db`, `orders-db`, `events-db`) with healthchecks
  - RabbitMQ (`rabbitmq:3-management`) with healthcheck
  - Service stubs for all 5 microservices + Kong
  - Named volumes for each database (`seats_data`, `users_data`, `orders_data`, `events_data`)
  - All `depends_on` with `condition: service_healthy` so services only start after deps are ready
  - See `INSTRUCTIONS.md` Section 4 for full example YAML
- [x] Write `docker-compose.dev.yml` with:
  - Volume mounts for each service's `src/` directory (hot-reload without rebuild)
  - `FLASK_DEBUG: "1"` and `FLASK_ENV: development` per service
- [x] Write `rabbitmq/definitions.json` with:
  - `seat.hold.exchange` (direct, durable)
  - `seat.hold.queue` with `x-message-ttl: 300000` and `x-dead-letter-exchange: seat.release.exchange`
  - `seat.release.exchange` (direct, durable) — the Dead Letter Exchange
  - `seat.release.queue` (durable) — consumed by Inventory Service
  - Bindings: `seat.hold.exchange → seat.hold.queue`, `seat.release.exchange → seat.release.queue`
- [x] Write `rabbitmq/rabbitmq.conf` to load definitions on startup:
  - `load_definitions = /etc/rabbitmq/definitions.json`
- [x] Add a minimal `Dockerfile` to each service folder (curl added for healthchecks)
- [x] Run `docker compose up --build` — all 11 containers started healthy ✅
- [x] Confirm RabbitMQ management UI is reachable at `localhost:15672` (default: guest/guest)
- [x] Confirm all 4 Postgres instances are reachable on ports 5433-5436
- [x] Confirm all health checks pass (`docker compose ps` shows `healthy` for all services)
- [ ] Verify `docker-compose.dev.yml` works: run with both files, edit a source file and confirm Flask auto-restarts

---

## Phase 2 — Database Setup

- [ ] **seats_db**: Write `inventory-service/init.sql`:
  - `seats` table — all columns from `INSTRUCTIONS.md` Section 3 (`seat_id UUID PK`, `event_id`, `owner_user_id`, `status ENUM(AVAILABLE/HELD/SOLD/CHECKED_IN)`, `held_by_user_id`, `held_until`, `qr_code_hash`, `price_paid`, `row_number`, `seat_number`, `created_at`, `updated_at`)
  - `entry_logs` table — `log_id`, `seat_id FK`, `scanned_at`, `scanned_by_staff_id`, `result ENUM`, `hall_id_presented`, `hall_id_expected`
  - Use `CREATE TABLE IF NOT EXISTS` throughout
- [ ] **users_db**: Write `user-service/init.sql`:
  - `users` table — `user_id`, `email UNIQUE`, `phone`, `password_hash`, `credit_balance NUMERIC(10,2)`, `two_fa_secret`, `is_flagged BOOLEAN`, `created_at`
- [ ] **orders_db**: Write `order-service/init.sql`:
  - `orders` table — `order_id`, `user_id`, `seat_id`, `event_id`, `status ENUM(PENDING/CONFIRMED/FAILED/REFUNDED)`, `credits_charged`, `verification_sid TEXT NULL` (for high-risk purchase OTP — cleared after verification), `created_at`, `confirmed_at`
  - `transfers` table — `transfer_id`, `seat_id`, `seller_user_id`, `buyer_user_id`, `initiated_by ENUM(SELLER/BUYER)`, `status ENUM(INITIATED/PENDING_OTP/COMPLETED/DISPUTED/REVERSED)`, `seller_otp_verified`, `buyer_otp_verified`, `seller_verification_sid TEXT NULL`, `buyer_verification_sid TEXT NULL` (both cleared after verification), `credits_amount`, `dispute_reason`, `created_at`, `completed_at`
  - Partial unique index: `CREATE UNIQUE INDEX idx_one_active_transfer_per_seat ON transfers (seat_id) WHERE status IN ('INITIATED', 'PENDING_OTP');`
- [ ] **events_db**: Write `event-service/init.sql`:
  - `venues` table — `venue_id`, `name`, `address`, `total_halls`, `created_at`
  - `events` table — `event_id`, `name`, `venue_id FK`, `hall_id`, `event_date`, `total_seats`, `pricing_tiers JSONB`
  - See `INSTRUCTIONS.md` Section 14 for the example seed SQL
- [ ] Mount init SQL files in `docker-compose.yml` via `/docker-entrypoint-initdb.d/init.sql` for each DB
- [ ] Seed `events_db`:
  - 1 venue: Singapore Indoor Stadium (use a fixed UUID so other seeds can reference it)
  - 1–2 events linked to that venue with pricing tiers (use fixed UUIDs)
- [ ] Seed `seats_db`:
  - 20+ seats linked to the seeded event's UUID, rows A–D, all status `AVAILABLE`
  - Use `INSERT ... ON CONFLICT DO NOTHING` for idempotency
- [ ] Seed `users_db`:
  - 2 test users: one normal (with credits), one with `is_flagged = true` (with credits)
  - Use `bcrypt`-hashed passwords in seed data
- [ ] Verify clean start: `docker compose down -v && docker compose up --build` — tables created, seeds populated

---

## Phase 3 — Event Service (simplest, start here)

- [ ] Scaffold Flask app in `event-service/src/app.py`
- [ ] Add to `requirements.txt`: `flask`, `flask-jwt-extended`, `flasgger`, `psycopg2-binary`, `sqlalchemy`
- [ ] Connect to `events_db` via SQLAlchemy or psycopg2 using env vars `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASS`
- [ ] Implement `GET /events`:
  - Returns list of events with nested venue info
  - Supports `?page=` and `?per_page=` query params (default 20, max 100)
  - Uses standard success response format from `API.md` Section 2
- [ ] Implement `GET /events/{event_id}`:
  - Returns event including `hall_id`, `venue_id`, pricing tiers, and a `seats` list showing availability
  - Returns `EVENT_NOT_FOUND` (404) if not found
  - Returns `INVALID_UUID` (400) if UUID is malformed
- [ ] Implement `GET /health`:
  - Checks DB connectivity
  - Returns `{"status": "healthy", ...}` on 200, `{"status": "unhealthy", ...}` on 503
- [ ] Add Flasgger docstrings to all endpoints
- [ ] Write a production-ready `Dockerfile` and confirm service runs in Docker
- [ ] Test with curl or Swagger UI at `localhost:5002/apidocs/`

---

## Phase 4 — User Service

- [ ] Scaffold Flask app in `user-service/src/app.py`
- [ ] Add to `requirements.txt`: `flask`, `flask-jwt-extended`, `flasgger`, `bcrypt`, `stripe`, `psycopg2-binary`, `sqlalchemy`, `requests`
- [ ] Connect to `users_db` via env vars
- [ ] Implement `POST /api/auth/register` 🔓 Public:
  - Hash password with bcrypt
  - Return `user_id` on success
  - Return `EMAIL_ALREADY_EXISTS` (409) if email taken
  - Validate email format, phone format, password length ≥ 8
- [ ] Implement `POST /api/auth/login` 🔓 Public:
  - Verify bcrypt hash
  - Issue `access_token` (15min TTL) and `refresh_token` (7 days TTL) via Flask-JWT-Extended
  - Return `user_id`, `email`, `credit_balance` in response body
- [ ] Implement `POST /api/auth/refresh`:
  - Accept `refresh_token` in `Authorization: Bearer` header
  - Return new `access_token`
- [ ] Implement `POST /api/auth/logout`:
  - Add JWT to blocklist (in-memory or Redis)
- [ ] Implement `GET /users/{user_id}`:
  - Return full user profile (exclude `password_hash`)
  - Return `USER_NOT_FOUND` (404) if not found
- [ ] Implement `GET /users/{user_id}/risk`:
  - Returns `{"is_flagged": bool}` — used by Orchestrator to decide if OTP is required
- [ ] Implement `POST /credits/deduct {user_id, amount}`:
  - `SELECT FOR UPDATE` on user row to prevent race conditions
  - Check `credit_balance >= amount`, deduct atomically
  - Return `INSUFFICIENT_CREDITS` (402) if insufficient
- [ ] Implement `POST /credits/refund {user_id, amount}`:
  - Add back credits — called by Orchestrator during compensation flows
- [ ] Implement `POST /credits/transfer {from_user_id, to_user_id, amount}`:
  - Atomic credit swap in a single DB transaction — used in P2P transfer
- [ ] Implement `POST /otp/send {user_id}`:
  - Looks up user's `phone` from DB
  - Calls SMU API `POST /SendOTP {Mobile: phone}` — returns `{VerificationSid, Success, ErrorMessage}`
  - **Store `VerificationSid`** — persist on the related transfer/order record or in a short-TTL Redis key keyed by `user_id`; required for verification
  - Return error if `Success == false`
- [ ] Implement `POST /otp/verify {user_id, otp_code}`:
  - Retrieve stored `VerificationSid` for this user/context
  - Calls SMU API `POST /VerifyOTP {VerificationSid, Code: otp_code}` — returns `{Success, Status, ErrorMessage}`
  - Treat `Status == "approved"` as verified; `Status == "pending"` as wrong code; `Status == "expired"` as expired
  - Track retry count; after 3 failures return `OTP_MAX_RETRIES`
- [ ] Implement Stripe webhook `POST /api/webhooks/stripe` 🔓 Public:
  - Validate Stripe signature using `STRIPE_WEBHOOK_SECRET`
  - On `payment.succeeded`: add credits to user's `credit_balance`
- [ ] Implement `GET /health` — check DB connectivity
- [ ] Add Flasgger docstrings to all endpoints
- [ ] Write `Dockerfile` and test all endpoints end-to-end

---

## Phase 5 — Order Service

- [ ] Scaffold Flask app in `order-service/src/app.py`
- [ ] Add to `requirements.txt`: `flask`, `flasgger`, `psycopg2-binary`, `sqlalchemy`
- [ ] Connect to `orders_db` via env vars
- [ ] Implement `POST /orders {user_id, seat_id, event_id, credits_charged}`:
  - Create order record with status `PENDING`
  - Return `order_id`
- [ ] Implement `PATCH /orders/{order_id} {status}`:
  - Update status to `CONFIRMED`, `FAILED`, or `REFUNDED`
  - Return `ORDER_NOT_FOUND` (404) if not found
- [ ] Implement `GET /orders?seat_id=`:
  - Fetch order by `seat_id` — used in Scenario 3 verification to confirm `CONFIRMED` order exists
- [ ] Implement `POST /transfers {seat_id, seller_user_id, buyer_user_id, initiated_by, credits_amount}`:
  - Create transfer record with status `INITIATED`
  - Return `transfer_id`
- [ ] Implement `PATCH /transfers/{transfer_id} {status, seller_otp_verified?, buyer_otp_verified?}`:
  - Update transfer through its lifecycle states
- [ ] Implement `POST /transfers/{transfer_id}/dispute {reason}`:
  - Set status → `DISPUTED`, store `dispute_reason`
- [ ] Implement `POST /transfers/{transfer_id}/reverse`:
  - Set status → `REVERSED`
- [ ] Implement `GET /health` — check DB connectivity
- [ ] Add Flasgger docstrings to all endpoints
- [ ] Write `Dockerfile` and test all endpoints

---

## Phase 6 — Inventory Service (gRPC)

- [ ] Define `inventory-service/src/proto/inventory.proto` with the following RPCs:
  - `ReserveSeat(seat_id, user_id)` → `{success, held_until}` — sets status `HELD`
  - `ConfirmSeat(seat_id, user_id)` → `{success}` — sets status `SOLD`, `owner_user_id`
  - `ReleaseSeat(seat_id)` → `{success}` — sets status `AVAILABLE`, clears held fields
  - `UpdateOwner(seat_id, new_owner_id)` → `{success}` — for P2P transfer
  - `VerifyTicket(seat_id)` → `{status, owner_user_id, event_id}` — read-only
  - `MarkCheckedIn(seat_id)` → `{success}` — sets status `CHECKED_IN`, writes `entry_log`
  - `GetSeatOwner(seat_id)` → `{owner_user_id, status}` — ownership check
- [ ] Generate Python gRPC stubs from `.proto` using `grpc_tools.protoc`
- [ ] Implement `lock_service.py` — `ReserveSeat` using `SELECT FOR UPDATE NOWAIT`
  - On lock failure (another user holds the row): raise gRPC error → Orchestrator returns `SEAT_UNAVAILABLE`
- [ ] Implement `ownership_service.py` — `UpdateOwner`, `ConfirmSeat`
- [ ] Implement `verification_service.py` — `VerifyTicket`, `MarkCheckedIn` (writes `entry_logs`)
- [ ] Implement `ReleaseSeat` — sets `status = AVAILABLE`, clears `held_by_user_id`, `held_until`
- [ ] Implement `seat_release_consumer.py`:
  - Listens to `seat.release.queue` via `pika`
  - On message: call `ReleaseSeat(seat_id)` and update the pending order to `FAILED` via HTTP call to Order Service
  - Use `basic_ack` on success, `basic_nack(requeue=True)` on failure
  - See `INSTRUCTIONS.md` Section 8 for full consumer code
- [ ] Start consumer in a separate **daemon thread** alongside the gRPC server in `main.py`
- [ ] Implement HTTP sidecar health endpoint `GET /health` on port 8080:
  - Check `seats_db` connectivity and RabbitMQ connectivity
- [ ] Write `Dockerfile` and test gRPC calls with `grpcurl` or a Python test script

---

## Phase 7 — Orchestrator Service

- [ ] Scaffold Flask app in `orchestrator-service/src/app.py`
- [ ] Add to `requirements.txt`: `flask`, `flask-jwt-extended`, `flasgger`, `grpcio`, `grpcio-tools`, `pika`, `cryptography`, `httpx`, `requests`
- [ ] Set up gRPC client stub to connect to `inventory-service:50051`
- [ ] Set up HTTP clients (httpx or requests) for User, Order, and Event services using env vars
- [ ] Set up RabbitMQ publisher connection (publish to `seat.hold.exchange`)
- [ ] Implement structured JSON logging middleware:
  - Generate a `correlation_id` (UUID) per request
  - Attach to `X-Correlation-ID` HTTP header for downstream REST calls
  - Attach to `correlation-id` gRPC metadata for downstream gRPC calls
  - Include in every log line — see `INSTRUCTIONS.md` Section 13 for the `JSONFormatter` code
- [ ] Implement QR code util in `utils/qr_util.py`:
  - `generate_qr(seat_id, user_id, hall_id)` → AES-256-GCM encrypted base64 string
  - `decrypt_qr(payload)` → decoded JSON dict or raise error
  - Use `QR_ENCRYPTION_KEY` from env (32 bytes), random 12-byte IV per generation
  - Output format: `base64(IV ∥ ciphertext ∥ auth_tag)`
  - See `INSTRUCTIONS.md` Section 7.1 for payload structure and encryption details

### Scenario 1 — Purchase Flow

- [ ] Implement `POST /api/reserve` in `purchase_routes.py`:
  - Call Inventory gRPC `ReserveSeat(seat_id, user_id)`
  - Handle `NOWAIT` lock failure → return `SEAT_UNAVAILABLE` (409) — no compensation needed
  - On success: publish TTL message `{seat_id, user_id, order_id, reserved_at}` to `seat.hold.exchange`
  - If RabbitMQ publish fails: call `ReleaseSeat` gRPC to undo hold, return `INTERNAL_ERROR`
  - Return `{order_id, seat_id, status: "HELD", held_until, ttl_seconds}` on success
- [ ] Implement `POST /api/pay` in `purchase_routes.py`:
  - Check `user.is_flagged` via User Svc `GET /users/{user_id}/risk` — if true, return `OTP_REQUIRED` (428)
  - Check seat is still `HELD` — if TTL expired, return `HOLD_EXPIRED` (410)
  - Call User Svc `POST /credits/deduct {user_id, amount}`
  - If deduct fails (insufficient): return `INSUFFICIENT_CREDITS` (402) — seat stays held, DLX will auto-release
  - Call Order Svc `POST /orders` → get `order_id`, set status `CONFIRMED`
  - If Order creation fails: call `POST /credits/refund` to reverse deduction → return `INTERNAL_ERROR`
  - Call Inventory gRPC `ConfirmSeat(seat_id, user_id)` — status → `SOLD`
  - If ConfirmSeat fails: call `POST /credits/refund` + update order → `FAILED` → return `INTERNAL_ERROR`
  - Generate QR code with `generate_qr(seat_id, user_id, hall_id)`
  - Return `{order_id, seat_id, status: "CONFIRMED", credits_charged, remaining_balance, qr_payload}`
  - **Compensation matrix:** see `INSTRUCTIONS.md` Section 5
- [ ] Implement `POST /api/verify-otp` — verify OTP for high-risk users:
  - Accepts `{user_id, otp_code, context, reference_id}`
  - Calls User Svc `POST /otp/verify`
  - On success: mark OTP as verified for the given `context` (purchase / transfer)

### Scenario 2 — P2P Transfer

- [ ] Implement `POST /api/transfer/initiate` in `transfer_routes.py`:
  - Validate: seller owns seat (`GetSeatOwner`), seat status is `SOLD`
  - Validate: no pending transfer for this seat (query Order Svc)
  - Block self-transfer: return `SELF_TRANSFER` (400) if `seller_user_id == buyer_user_id`
  - Validate: buyer has sufficient credits (User Svc `GET /users/{buyer_id}`)
  - Create transfer record via Order Svc `POST /transfers` → status `INITIATED`
  - Trigger OTP for both seller and buyer via User Svc `POST /otp/send` for each user
  - Update transfer → `PENDING_OTP`
  - Return `{transfer_id, seat_id, status: "PENDING_OTP"}`
- [ ] Implement `POST /api/transfer/confirm` in `transfer_routes.py`:
  - Verify both OTPs via User Svc `POST /otp/verify` for seller and buyer
  - On OTP failure: allow retries up to 3 — after 3 failures, update transfer → `FAILED`
  - Execute atomic swap:
    1. User Svc `POST /credits/transfer {from_user_id: buyer, to_user_id: seller, amount}`
    2. Inventory gRPC `UpdateOwner(seat_id, buyer_id)` — if fails, reverse credit transfer and set transfer → `FAILED`
    3. Order Svc `PATCH /transfers/{transfer_id}` → `COMPLETED`
  - Generate new QR code for the new owner (buyer's `user_id`)
  - Return `{transfer_id, status: "COMPLETED", new_owner_user_id, credits_transferred}`
- [ ] Implement `POST /api/transfer/dispute`:
  - Delegate to Order Svc `POST /transfers/{transfer_id}/dispute`
  - Only seller or buyer can dispute — check JWT user_id
- [ ] Implement `POST /api/transfer/reverse`:
  - Reverse: `UpdateOwner` back to seller + credit reversal + Order Svc `reverse`

### Scenario 3 — QR Verification

- [ ] Implement `POST /api/verify` in `verification_routes.py`:
  - Decrypt QR payload using `decrypt_qr(qr_payload)` — return `QR_INVALID` (400) if fails
  - Validate timestamp: `NOW - generated_at <= 60 seconds` — return (result: `EXPIRED`) if stale
  - Fan out **parallel** calls to 3 services:
    - Inventory gRPC `VerifyTicket(seat_id)` → `{status, owner_user_id, event_id}`
    - Order Svc `GET /orders?seat_id=` → confirm `CONFIRMED` order exists
    - Event Svc `GET /events/{event_id}` → get expected `hall_id`
  - Run all business rule checks (see `INSTRUCTIONS.md` Section 7 validation table)
  - On all checks pass: call Inventory gRPC `MarkCheckedIn(seat_id)`
  - Write `entry_log` for every scan (pass or fail) — note: log write failure is non-critical
  - Return `{result, seat_id, row_number, seat_number, owner_name, message}` — all rejections return HTTP 200

### Ticket Endpoints

- [ ] Implement `GET /api/tickets`:
  - Read JWT to get `user_id`
  - Query Inventory service for all seats where `owner_user_id == user_id` (add a gRPC RPC or HTTP query)
  - For each seat, fan out to Event Service to get event name / date
  - Return list with nested `event` object, `row_number`, `seat_number`, `status`, `price_paid`, `purchased_at`
- [ ] Implement `GET /api/tickets/{seat_id}/qr`:
  - Verify JWT user_id == `seat.owner_user_id` — else `NOT_SEAT_OWNER` (403)
  - Verify seat is `SOLD` — else `SEAT_UNAVAILABLE` (409)
  - Generate fresh QR with current timestamp via `generate_qr(seat_id, user_id, hall_id)`
  - Return `{qr_payload, generated_at, expires_at, ttl_seconds: 60}`

### Credit Endpoints

- [ ] Implement `GET /api/credits/balance`:
  - Reads JWT user_id, calls User Svc `GET /users/{user_id}`, return `credit_balance`
- [ ] Implement `POST /api/credits/topup {amount}`:
  - Call User Svc to create Stripe Payment Intent
  - Return `{client_secret, amount, currency}` for frontend Stripe.js to complete

### Orchestrator Health

- [ ] Implement `GET /health`:
  - Ping all 4 downstream services (Inventory, User, Order, Event) and RabbitMQ
  - Return `{"status": "healthy/unhealthy", "checks": {...}}`
- [ ] Add Flasgger docstrings to all public endpoints
- [ ] Write `Dockerfile` and confirm service starts cleanly

---

## Phase 8 — API Gateway (Kong)

- [ ] Write `api-gateway/kong.yml` (declarative DB-less mode) with:
  - Routes for all Orchestrator public endpoints pointing to `http://orchestrator-service:5003`
  - Route for `GET /api/events` and `GET /api/events/{event_id}` — these should be public (no JWT)
  - Route for `POST /api/auth/*` — public (no JWT)
  - Route for `POST /api/webhooks/stripe` — public (no JWT), but uses Stripe signature
  - All other routes — JWT required
- [ ] Add Kong JWT plugin config:
  - Validate JWT via `JWT_SECRET`, extract `sub` claim as user_id
  - See `INSTRUCTIONS.md` Section 11 for plugin YAML
- [ ] Add Kong CORS plugin config:
  - Allow origins: `localhost:3000` (dev) + production domain
  - Allow methods: GET, POST, PATCH, DELETE, OPTIONS
  - Allow headers: `Authorization`, `Content-Type`
  - `credentials: true`
- [ ] Add rate limiting plugin to protect against surge traffic (e.g., 100 req/min per consumer)
- [ ] Write `api-gateway/Dockerfile` (or use `image: kong:3.6` directly)
- [ ] Test that requests through `localhost:8000` correctly reach the Orchestrator
- [ ] Verify JWT is rejected without a valid token on protected routes

---

## Phase 9 — End-to-End Testing

> **Pre-conditions before starting Phase 9:**
>
> - `docker compose up --build` is clean with all services `healthy`
> - Seed data is present (Phase 2 seed verified)
> - You have the test user credentials (from seed data)
> - You have registered a user via `POST /api/auth/register` and hold a valid JWT

### Setup

- [ ] Register 2 test users via API: a normal user and explicitly mark one `is_flagged = true` in DB
- [ ] Top up credits for both users (either via Stripe test mode or direct DB update for testing)

### Scenario 1 — Purchase

- [ ] Test happy path: reserve → pay → confirm booking (verify seat becomes `SOLD` in DB)
- [ ] Test seat lock contention: two concurrent users reserve same seat → second gets `SEAT_UNAVAILABLE`
- [ ] Test abandonment: reserve → wait for TTL (5 min) → confirm seat returns to `AVAILABLE` via DLX
- [ ] Test high-risk user: reserve → pay → receive `OTP_REQUIRED` → verify OTP → complete pay
- [ ] Test insufficient credits: reserve with user who has < event price → pay → `INSUFFICIENT_CREDITS`
- [ ] Test compensation: mock `ConfirmSeat` gRPC failure → verify credits are refunded and order is `FAILED`
- [ ] Test hold expired: reserve, wait for TTL, then call `/api/pay` → `HOLD_EXPIRED`

### Scenario 2 — Transfer

- [ ] Test success path: User A owns seat → initiate → both submit OTPs → confirm → verify ownership & credits changed
- [ ] Test seller-initiated vs. buyer-initiated transfer (both should work)
- [ ] Test OTP failure: submit wrong OTP → transfer stays `PENDING_OTP`
- [ ] Test max OTP retries (3 failures) → transfer auto-cancelled → status `FAILED`
- [ ] Test duplicate transfer: start second transfer for same seat while one is `PENDING_OTP` → `TRANSFER_IN_PROGRESS`
- [ ] Test self-transfer → `SELF_TRANSFER`
- [ ] Test dispute: complete transfer → call `/dispute` → status `DISPUTED`
- [ ] Test reverse: dispute a transfer → call `/reverse` → ownership and credits restored
- [ ] Test QR invalidation: after transfer, old owner's QR should be rejected (user_id mismatch) on verify

### Scenario 3 — Verification

- [ ] Test valid scan → result `SUCCESS`, seat becomes `CHECKED_IN` in DB, `entry_log` written
- [ ] Test duplicate scan with same QR → result `DUPLICATE` (200, not error)
- [ ] Test scan of `HELD` seat (payment not completed) → result `UNPAID`
- [ ] Test non-existent seat_id in QR → result `NOT_FOUND`
- [ ] Test wrong hall (QR `hall_id` ≠ event `hall_id`) → result `WRONG_HALL`
- [ ] Test expired QR: generate QR, wait >60 seconds, scan → result `EXPIRED`
- [ ] Test old owner's QR after transfer → rejected (user_id mismatch)

---

## Phase 10 — Polish

- [ ] Add standard error response format (`{"success": false, "error_code": ..., "message": ...}`) to every service — see `API.md` Section 2
- [ ] Add request validation using Pydantic or manual checks (reject malformed UUIDs, missing fields, negative amounts)
- [ ] Add structured JSON logging with correlation IDs to every service — see `INSTRUCTIONS.md` Section 13
- [ ] Complete all Flasgger/Swagger docstrings for every endpoint; verify Swagger UI loads at each service port
- [ ] Set up shared Postman workspace:
  - Create workspace `TicketRemaster` with collections per scenario (Auth, Purchase, Transfer, Verification)
  - Set collection variable `baseUrl` and auto-capture `accessToken` after login
  - Export collection to `postman/TicketRemaster.postman_collection.json` and commit to repo
  - See `INSTRUCTIONS.md` Section 15 for setup details
- [ ] Write `.github/workflows/ci.yml`:
  - Trigger on push and PR to `main`
  - Steps: `flake8` lint, `black --check`, run `pytest` (per service)
- [ ] Update root `README.md` with final setup, run, and testing instructions
- [ ] Do a full clean run: `docker compose down -v && docker compose up --build` — confirm everything builds from scratch with no errors
- [ ] Verify CI pipeline passes on GitHub (check Actions tab on PR)
