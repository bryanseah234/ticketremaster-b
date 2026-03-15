# TicketRemaster — Implementation Task List
### Stack: Python · Flask · PostgreSQL · RabbitMQ · gRPC · OutSystems · Docker · Kubernetes

---

## Phase 0 — Project Setup

- [ ] Initialise monorepo folder structure (one folder per service and per orchestrator)
- [ ] Create `proto/seat_inventory.proto` — shared gRPC contract at repo root
- [ ] Set up shared `docker-compose.yml` at root level
- [ ] Set up shared `.env.example` with all environment variable keys
- [ ] Create a base `Dockerfile` template to reuse across all services
- [ ] Create a base `requirements.txt` with shared dependencies (flask, flask-sqlalchemy, flask-migrate, psycopg2-binary, python-dotenv, gunicorn)
- [ ] Set up a shared Postman or Bruno collection for API testing
- [ ] Initialise a Git repository with a `.gitignore` (include `.env`, `__pycache__`, `*.pyc`, `migrations/`)
- [ ] Generate gRPC Python stubs from `proto/seat_inventory.proto` using `grpc_tools.protoc` and commit the generated files

---

## Phase 1 — Foundation Services (no dependencies)

These services have no dependencies on other services and can be built first.
Each follows the same pattern: scaffold → model → migrate → routes → seed → test → docker-compose.

### 1.1 User Service
- [ ] Scaffold service (`app.py`, `models.py`, `routes.py`, `requirements.txt`, `Dockerfile`)
- [ ] Set up Flask app factory with SQLAlchemy and Flask-Migrate
- [ ] Implement `GET /health`
- [ ] Create `users` table migration (`flask db init` → `flask db migrate` → `flask db upgrade`)
- [ ] Implement `POST /users` — create user (stores pre-hashed password and salt — no bcrypt here)
- [ ] Implement `GET /users/<user_id>` — get by ID
- [ ] Implement `GET /users/by-email/<email>` — get by email
- [ ] Implement `PATCH /users/<user_id>` — partial update
- [ ] Write unit tests
- [ ] Add service and its own Postgres container to `docker-compose.yml`
- [ ] Verify boots cleanly with `docker compose up`

### 1.2 Venue Service
- [ ] Scaffold service
- [ ] Set up Flask app factory with SQLAlchemy and Flask-Migrate
- [ ] Implement `GET /health`
- [ ] Create `venues` table migration
- [ ] Write `seed.py` — seed at least 2 venues with capacity, coordinates, address
- [ ] Run `seed.py` via `docker compose exec` and verify records exist
- [ ] Implement `GET /venues` — list all active venues
- [ ] Implement `GET /venues/<venue_id>` — get by ID
- [ ] Write unit tests
- [ ] Add to `docker-compose.yml`

### 1.3 Seat Service
- [ ] Scaffold service
- [ ] Set up Flask app factory with SQLAlchemy and Flask-Migrate
- [ ] Implement `GET /health`
- [ ] Create `seats` table migration
- [ ] Write `seed.py` — seed all seats for each seeded venue (rows A–Z, seats 1–N based on venue capacity)
- [ ] Run `seed.py` and verify seat records exist for all venues
- [ ] Implement `GET /seats/venue/<venue_id>` — get all seats for a venue
- [ ] Write unit tests
- [ ] Add to `docker-compose.yml`

### 1.4 Credit Service (OutSystems — external)
- [ ] Build `POST /credits` endpoint in OutSystems — initialise zero balance record for a new user
- [ ] Build `GET /credits/<user_id>` endpoint in OutSystems — return current credit balance
- [ ] Build `PATCH /credits/<user_id>` endpoint in OutSystems — update balance (accepts new absolute balance, not delta); confirm response includes updated `creditBalance` so orchestrators do not need a second GET call
- [ ] Secure OutSystems REST API with an API key
- [ ] Confirm all three JSON response shapes match the contracts in the API reference PDF
- [ ] Add `CREDIT_SERVICE_URL` and `OUTSYSTEMS_API_KEY` to `.env.example`
- [ ] Add `OUTSYSTEMS_API_KEY` to Kubernetes Secrets list for Phase 8
- [ ] Test all three endpoints manually via Postman before building any orchestrator that calls them
- [ ] Do NOT add Credit Service to `docker-compose.yml` — it is an external OutSystems service

### 1.5 Credit Transaction Service
- [ ] Scaffold service
- [ ] Set up Flask app factory with SQLAlchemy and Flask-Migrate
- [ ] Implement `GET /health`
- [ ] Create `credit_txns` table migration
- [ ] Implement `POST /credit-transactions` — log a credit movement (delta, reason, referenceId)
- [ ] Implement `GET /credit-transactions/user/<user_id>` — get history (paginated)
- [ ] Implement `GET /credit-transactions/reference/<reference_id>` — look up by referenceId (for Stripe idempotency check)
- [ ] Write unit tests
- [ ] Add to `docker-compose.yml`

---

## Phase 2 — Event & Seat Inventory Services

Depends on: Venue Service, Seat Service (seeded data must exist)

### 2.1 Event Service
- [ ] Scaffold service
- [ ] Set up Flask app factory with SQLAlchemy and Flask-Migrate
- [ ] Implement `GET /health`
- [ ] Create `events` table migration
- [ ] Write `seed.py` — seed at least 2 events pointing to seeded venues
- [ ] Run `seed.py` and verify event records exist
- [ ] Implement `GET /events` — list all events
- [ ] Implement `GET /events/<event_id>` — get by ID
- [ ] Implement `POST /events` — create event (admin only)
- [ ] Write unit tests
- [ ] Add to `docker-compose.yml`

### 2.2 Seat Inventory Service
- [ ] Scaffold service (`app.py`, `models.py`, `routes.py`, `grpc_server.py`, `server.py`, `requirements.txt`, `Dockerfile`)
- [ ] Add `grpcio` and `grpcio-tools` to `requirements.txt`
- [ ] Copy generated gRPC stubs (`seat_inventory_pb2.py`, `seat_inventory_pb2_grpc.py`) into this service
- [ ] Set up Flask app factory with SQLAlchemy and Flask-Migrate
- [ ] Implement `GET /health`
- [ ] Create `seat_inventory` table migration
- [ ] Write `seed.py` — create one inventory record per seat per event (status: available)
- [ ] Run `seed.py` and verify inventory records exist
- [ ] Implement gRPC `HoldSeat` — with `SELECT FOR UPDATE` pessimistic lock
- [ ] Implement gRPC `ReleaseSeat`
- [ ] Implement gRPC `SellSeat`
- [ ] Implement gRPC `GetSeatStatus`
- [ ] Implement `GET /inventory/event/<event_id>` — seat map (REST)
- [ ] Implement `server.py` — starts gRPC server (port 50051) and Flask REST server (port 5000) in parallel threads
- [ ] Write unit tests including concurrent hold race condition test (two simultaneous HoldSeat requests for same seat — assert only one succeeds)
- [ ] Add to `docker-compose.yml` exposing both ports 5000 and 50051

---

## Phase 3 — Ticket, Marketplace & Transfer Services

Depends on: User Service, Event Service, Venue Service, Seat Inventory Service

### 3.1 Ticket Service
- [ ] Scaffold service
- [ ] Set up Flask app factory with SQLAlchemy and Flask-Migrate
- [ ] Implement `GET /health`
- [ ] Create `tickets` table migration
- [ ] Implement `POST /tickets` — create ticket record (generates initial qrHash placeholder)
- [ ] Implement `GET /tickets/<ticket_id>` — get by ID
- [ ] Implement `GET /tickets/owner/<owner_id>` — get all tickets by owner
- [ ] Implement `GET /tickets/qr/<qr_hash>` — look up by QR hash
- [ ] Implement `PATCH /tickets/<ticket_id>` — partial update (status, ownerId, qrHash, qrTimestamp)
- [ ] Write unit tests
- [ ] Add to `docker-compose.yml`

### 3.2 Ticket Log Service
- [ ] Scaffold service
- [ ] Set up Flask app factory with SQLAlchemy and Flask-Migrate
- [ ] Implement `GET /health`
- [ ] Create `ticket_logs` table migration
- [ ] Implement `POST /ticket-logs` — create scan log entry
- [ ] Implement `GET /ticket-logs/ticket/<ticket_id>` — get all scan logs for a ticket
- [ ] Write unit tests
- [ ] Add to `docker-compose.yml`

### 3.3 Marketplace Service
- [ ] Scaffold service
- [ ] Set up Flask app factory with SQLAlchemy and Flask-Migrate
- [ ] Implement `GET /health`
- [ ] Create `listings` table migration
- [ ] Implement `POST /listings` — create listing (status: active)
- [ ] Implement `GET /listings` — get all active listings
- [ ] Implement `GET /listings/<listing_id>` — get by ID
- [ ] Implement `PATCH /listings/<listing_id>` — update status (active / completed / cancelled)
- [ ] Write unit tests
- [ ] Add to `docker-compose.yml`

### 3.4 Transfer Service
- [ ] Scaffold service
- [ ] Set up Flask app factory with SQLAlchemy and Flask-Migrate
- [ ] Implement `GET /health`
- [ ] Create `transfers` table migration
- [ ] Implement `POST /transfers` — create transfer record
- [ ] Implement `GET /transfers/<transfer_id>` — get by ID
- [ ] Implement `PATCH /transfers/<transfer_id>` — update fields (status, OTP flags, SIDs, completedAt)
- [ ] Write unit tests
- [ ] Add to `docker-compose.yml`

---

## Phase 4 — External Wrappers

### 4.1 Stripe Wrapper
- [ ] Scaffold service
- [ ] Add `stripe` to `requirements.txt`
- [ ] Implement `GET /health`
- [ ] Implement `POST /stripe/create-payment-intent` — create Payment Intent, attach userId in metadata
- [ ] Implement `POST /stripe/webhook` — verify Stripe signature, extract userId and credits, forward result
- [ ] Test with Stripe CLI: `stripe listen --forward-to localhost:PORT/stripe/webhook`
- [ ] Verify webhook signature rejection works (send a request without a valid signature)
- [ ] Add to `docker-compose.yml`

### 4.2 OTP Wrapper
- [ ] Scaffold service
- [ ] Implement `GET /health`
- [ ] Implement `POST /otp/send` — call SMU Notification API, return SID
- [ ] Implement `POST /otp/verify` — call SMU Notification API with SID + OTP, return pass/fail
- [ ] Add to `docker-compose.yml`

---

## Phase 5 — RabbitMQ Setup

Depends on: All atomic services running

- [ ] Add RabbitMQ (`rabbitmq:3-management`) to `docker-compose.yml` with ports 5672 and 15672
- [ ] Add `pika` to `requirements.txt` of any service that publishes or consumes
- [ ] Write `queue_setup.py` — declares Seat Hold TTL Queue, DLX exchange, dead letter queue, and Seller Notification Queue
- [ ] Call `queue_setup.py` on startup of Ticket Purchase Orchestrator and Transfer Orchestrator
- [ ] Verify TTL expiry and DLX routing manually via RabbitMQ management UI (http://localhost:15672)
- [ ] Verify Seller Notification Queue publishes and consumes correctly

---

## Phase 6 — Orchestrators

Build in order — each one validates the integration pattern for the next.

### 6.1 Auth Orchestrator
Depends on: User Service, Credit Service

- [ ] Scaffold orchestrator (`app.py`, `routes.py`, `middleware.py`, `requirements.txt`, `Dockerfile`)
- [ ] Add `PyJWT` and `bcrypt` to `requirements.txt`
- [ ] Add `requests` to `requirements.txt`
- [ ] Implement `GET /health`
- [ ] Build `@require_auth` JWT decorator in `middleware.py` (to be reused in all orchestrators)
- [ ] Build `@require_staff` JWT decorator in `middleware.py`
- [ ] Build `call_service()` helper for internal HTTP calls with timeout and error handling
- [ ] Implement `POST /auth/register` — hash password, create user via User Service, initialise zero credit balance via OutSystems Credit Service, compensate (delete user) if OutSystems call fails
- [ ] Implement `POST /auth/login` — validate credentials with bcrypt, issue JWT (include venueId for staff)
- [ ] Implement `GET /auth/me` — decode JWT and return user profile
- [ ] Write integration tests
- [ ] Add to `docker-compose.yml`

### 6.2 Event Orchestrator
Depends on: Event Service, Venue Service, Seat Service, Seat Inventory Service

- [ ] Scaffold orchestrator
- [ ] Add `requests` to `requirements.txt`
- [ ] Implement `GET /health`
- [ ] Implement `GET /events` — list events (no JWT required)
- [ ] Implement `GET /events/<event_id>` — event detail with venue (no JWT required)
- [ ] Implement `GET /events/<event_id>/seats` — seat map (no JWT required)
- [ ] Implement `GET /events/<event_id>/seats/<inventory_id>` — single seat detail (no JWT required)
- [ ] Write integration tests
- [ ] Add to `docker-compose.yml`

### 6.3 Credit Orchestrator
Depends on: Credit Service (OutSystems), Credit Transaction Service, Stripe Wrapper

- [ ] Scaffold orchestrator
- [ ] Copy `middleware.py` from Auth Orchestrator
- [ ] Add `requests` to `requirements.txt`
- [ ] Implement `GET /health`
- [ ] Implement `call_credit_service()` helper — wraps `call_service()` with OutSystems API key header injected from `OUTSYSTEMS_API_KEY` env var
- [ ] Implement `GET /credits/balance` — get balance for authenticated user from OutSystems
- [ ] Implement `POST /credits/topup/initiate` — call Stripe Wrapper, return clientSecret
- [ ] Implement `POST /credits/topup/webhook` — verify Stripe result, check idempotency via Credit Transaction Service, update balance in OutSystems, log transaction to Credit Transaction Service
- [ ] Implement `GET /credits/transactions` — get paginated transaction history from Credit Transaction Service
- [ ] Write integration tests using Stripe test mode
- [ ] Add to `docker-compose.yml`

### 6.4 Ticket Purchase Orchestrator
Depends on: Seat Inventory Service (gRPC), Ticket Service, Credit Service (OutSystems), Credit Transaction Service, RabbitMQ

- [ ] Scaffold orchestrator
- [ ] Copy `middleware.py` from Auth Orchestrator
- [ ] Add `requests`, `grpcio`, `pika` to `requirements.txt`
- [ ] Copy gRPC stubs (`seat_inventory_pb2.py`, `seat_inventory_pb2_grpc.py`) into orchestrator
- [ ] Implement `GET /health`
- [ ] Set up gRPC client channel to Seat Inventory Service
- [ ] Implement `queue_setup.py` — declare Seat Hold TTL Queue and DLX on startup
- [ ] Start DLX consumer in background thread on app startup
- [ ] Implement DLX consumer handler — call gRPC `ReleaseSeat` for each expired hold message
- [ ] Implement `POST /purchase/hold/<inventory_id>` — call gRPC HoldSeat, publish TTL message, return heldUntil
- [ ] Implement `POST /purchase/confirm/<inventory_id>` — verify hold, check credits via OutSystems, call gRPC SellSeat, create ticket, deduct credits in OutSystems, log transaction to Credit Transaction Service
- [ ] Set `SEAT_HOLD_DURATION_SECONDS` as an environment variable (600 production, 10 for testing)
- [ ] Write integration tests including hold expiry scenario
- [ ] Add to `docker-compose.yml`

### 6.5 QR Orchestrator
Depends on: Ticket Service

- [ ] Scaffold orchestrator
- [ ] Copy `middleware.py` from Auth Orchestrator
- [ ] Add `requests` to `requirements.txt`
- [ ] Implement `GET /health`
- [ ] Implement `GET /tickets` — list all active tickets for authenticated user
- [ ] Implement `GET /tickets/<ticket_id>/qr` — generate fresh SHA-256 qrHash using ticketId + timestamp + QR_SECRET, update ticket record, return QR data
- [ ] Set `QR_SECRET` as environment variable (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Write integration tests including rejection of listed and used tickets
- [ ] Add to `docker-compose.yml`

### 6.6 Marketplace Orchestrator
Depends on: Ticket Service, Marketplace Service

- [ ] Scaffold orchestrator
- [ ] Copy `middleware.py` from Auth Orchestrator
- [ ] Add `requests` to `requirements.txt`
- [ ] Implement `GET /health`
- [ ] Implement `GET /marketplace` — browse all active listings with event and seat details
- [ ] Implement `POST /marketplace/list` — validate ticket ownership and status, set ticket to listed, create listing
- [ ] Implement `DELETE /marketplace/<listing_id>` — cancel listing, reset ticket to active
- [ ] Write integration tests
- [ ] Add to `docker-compose.yml`

### 6.7 Transfer Orchestrator
Depends on: Marketplace Service, Transfer Service, OTP Wrapper, Credit Service (OutSystems), Credit Transaction Service, Ticket Service, RabbitMQ

- [ ] Scaffold orchestrator
- [ ] Copy `middleware.py` from Auth Orchestrator
- [ ] Add `requests`, `pika` to `requirements.txt`
- [ ] Implement `GET /health`
- [ ] Implement `queue_setup.py` — declare Seller Notification Queue on startup
- [ ] Start Seller Notification Queue consumer in background thread on app startup
- [ ] Implement Seller Notification Queue consumer handler — notify seller (e.g. store notification flag or push via websocket)
- [ ] Implement `POST /transfer/initiate` — validate listing, check buyer credits, send buyer OTP via OTP Wrapper, create transfer record
- [ ] Implement `POST /transfer/<transfer_id>/buyer-verify` — verify buyer OTP, set buyerOtpVerified, publish seller notification message
- [ ] Implement `POST /transfer/<transfer_id>/seller-accept` — send seller OTP via OTP Wrapper, update transfer status
- [ ] Implement `POST /transfer/<transfer_id>/seller-verify` — verify seller OTP, re-check buyer balance via OutSystems, execute transfer (saga pattern: deduct buyer in OutSystems → credit seller in OutSystems → log both transactions → update ticket → complete listing → complete transfer; compensate in reverse on any failure)
- [ ] Implement `GET /transfer/<transfer_id>` — return transfer status (accessible by buyer and seller only)
- [ ] Implement `POST /transfer/<transfer_id>/cancel` — cancel in-progress transfer, reset ticket to listed, listing to active
- [ ] Write integration tests for full happy path
- [ ] Write integration tests for each failure scenario (buyer OTP fail, seller OTP fail, insufficient credits at execution)
- [ ] Add to `docker-compose.yml`

### 6.8 Ticket Verification Orchestrator
Depends on: Ticket Service, Event Service, Seat Inventory Service, Venue Service, Ticket Log Service

- [ ] Scaffold orchestrator
- [ ] Copy `middleware.py` from Auth Orchestrator
- [ ] Add `requests` to `requirements.txt`
- [ ] Implement `GET /health`
- [ ] Implement `POST /verify/scan` — full QR verification in correct check order:
  - [ ] Look up ticket by qrHash
  - [ ] Check QR TTL (60 seconds) — log expired if stale
  - [ ] Validate event is active
  - [ ] Confirm seat status is sold via Seat Inventory Service
  - [ ] Confirm ticket status is active
  - [ ] Check for duplicate scan via Ticket Log Service
  - [ ] Check venueId matches staff JWT venueId — return correct venue on mismatch
  - [ ] All pass: update ticket to used, log checked_in
- [ ] Write integration tests for each rejection scenario (expired, duplicate, wrong venue, invalid ticket)
- [ ] Add to `docker-compose.yml`

---

## Phase 7 — End-to-End Testing

Run all tests using your Postman or Bruno collection against the full stack running via `docker compose up`.

- [ ] Test Scenario 1: Full credit top-up flow (Stripe test mode — initiate → Stripe UI → webhook → balance updated)
- [ ] Test Scenario 2: Full ticket purchase flow (browse events → view seat map → hold seat → confirm purchase → ticket created)
- [ ] Test Scenario 2b: Hold expiry — set `SEAT_HOLD_DURATION_SECONDS=10`, select a seat, wait 10 seconds, confirm seat returns to available automatically
- [ ] Test Scenario 3: Full P2P transfer happy path (list ticket → buyer initiates → buyer OTP → seller accepts → seller OTP → credits swap → ticket ownership changes)
- [ ] Test Scenario 3b: Transfer cancellation mid-flow (cancel after buyer OTP verified — confirm listing reactivated and ticket returns to listed)
- [ ] Test Scenario 3c: Insufficient credits at execution time (manually drain buyer credits between initiation and seller verification — confirm INSUFFICIENT_CREDITS returned and credits not deducted)
- [ ] Test Scenario 4: Ticket verification all pass (scan valid ticket at correct venue — confirm checked_in)
- [ ] Test Scenario 4b: Expired QR rejection (wait 61 seconds after generating QR — confirm QR_EXPIRED)
- [ ] Test Scenario 4c: Duplicate scan rejection (scan same ticket twice — confirm DUPLICATE_SCAN on second scan)
- [ ] Test Scenario 4d: Wrong venue redirect (scan ticket at wrong venue — confirm WRONG_VENUE with correct venue details returned)

---

## Phase 8 — Docker & Kubernetes

### Docker Compose final checks
- [ ] Verify all services and orchestrators boot cleanly with `docker compose up`
- [ ] Confirm all inter-service communication uses Docker service names (not localhost)
- [ ] Confirm all services have `GET /health` returning 200
- [ ] Confirm all Postgres containers have `pg_isready` healthchecks
- [ ] Confirm all services have `restart: unless-stopped`
- [ ] Confirm `SEAT_HOLD_DURATION_SECONDS` and `QR_SECRET` are environment variables, not hardcoded

### Kubernetes migration
- [ ] Install Kompose
- [ ] Run `kompose convert -f docker-compose.yml` to generate base Kubernetes manifests
- [ ] Review generated Deployment and Service YAML files for each service
- [ ] Create `k8s/secrets.yaml` — move JWT_SECRET, STRIPE_SECRET_KEY, QR_SECRET, STRIPE_WEBHOOK_SECRET, OUTSYSTEMS_API_KEY out of plaintext Deployments
- [ ] Update all Deployments to reference secrets via `secretKeyRef`
- [ ] Add `livenessProbe` and `readinessProbe` (pointing at `GET /health`) to every Deployment
- [ ] Add resource requests and limits to every Deployment
- [ ] Add `HorizontalPodAutoscaler` for `seat-inventory-service` (minReplicas: 2, maxReplicas: 10, CPU target: 70%)
- [ ] Add `HorizontalPodAutoscaler` for `ticket-purchase-orchestrator` (minReplicas: 2, maxReplicas: 8, CPU target: 70%)
- [ ] Change all orchestrator Services from NodePort to ClusterIP
- [ ] Create `k8s/ingress.yaml` — single Ingress routing /auth, /events, /purchase, /credits, /marketplace, /transfer, /tickets, /verify to their respective orchestrators
- [ ] Test full stack on Minikube (`minikube start` → `eval $(minikube docker-env)` → `docker compose build` → `kubectl apply -f k8s/` → `minikube tunnel`)
