# TicketRemaster — Implementation Instructions
### Stack: Python · Flask · PostgreSQL · RabbitMQ · gRPC · OutSystems · Docker · Kubernetes

This document explains the reasoning behind the implementation order in `tasks.md` and provides detailed guidance for each phase.

---

## Why this order?

The build order follows a strict dependency graph — each layer can only be built once the layers it depends on are stable. The principle is:

```
Foundation services → Event & Inventory services → Ticket/Transfer/Marketplace services
→ External wrappers → RabbitMQ → Orchestrators (simple → complex)
→ E2E tests → Docker & Kubernetes
```

Never start an orchestrator until all the atomic services it calls are running and tested. Orchestrators are wiring, not logic — if the services underneath are broken, debugging the orchestrator becomes impossible.

---

## Phase 0 — Project Setup

### Folder structure
Organise as a monorepo with one folder per service. Each service is fully self-contained with its own `requirements.txt`, `Dockerfile`, and database migrations.

```
ticketremaster/
├── docker-compose.yml
├── .env.example
├── proto/
│   └── seat_inventory.proto        <- shared gRPC contract
├── services/
│   ├── user-service/
│   ├── event-service/
│   ├── venue-service/
│   ├── seat-service/
│   ├── seat-inventory-service/
│   ├── ticket-service/
│   ├── ticket-log-service/
│   ├── marketplace-service/
│   ├── transfer-service/
│   ├── credit-transaction-service/
│   ├── stripe-wrapper/
│   └── otp-wrapper/
└── orchestrators/
    ├── auth-orchestrator/
    ├── event-orchestrator/
    ├── credit-orchestrator/
    ├── ticket-purchase-orchestrator/
    ├── qr-orchestrator/
    ├── marketplace-orchestrator/
    ├── transfer-orchestrator/
    └── ticket-verification-orchestrator/
```

### Standard service structure
Every service and orchestrator follows the same internal layout:

```
user-service/
├── Dockerfile
├── requirements.txt
├── .env
├── app.py          <- Flask app factory, registers blueprints
├── models.py       <- SQLAlchemy models
├── routes.py       <- Flask route handlers
└── migrations/     <- Flask-Migrate / Alembic migration files
```

### Standard Dockerfile
All services use the same base pattern:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

Use gunicorn with at least 4 workers in all environments. Flask's built-in dev server is
single-threaded and will silently serialise concurrent requests. This matters critically
for the Seat Inventory Service under load.

For the Seat Inventory Service, the Dockerfile needs a custom entrypoint that starts
both the REST and gRPC servers:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000 50051
CMD ["python", "server.py"]
```

### Base requirements.txt
Every service shares this base set:

```
flask==3.0.3
flask-sqlalchemy==3.1.1
flask-migrate==4.0.7
psycopg2-binary==2.9.9
python-dotenv==1.0.1
gunicorn==22.0.0
```

Additional per-service dependencies are noted in each phase below.

### Health check endpoint
Every service must expose GET /health returning { "status": "ok" }. Add this to every
service before anything else — it is required for Docker health checks and Kubernetes
liveness probes.

```python
@app.route('/health')
def health():
    return {"status": "ok"}, 200
```

### Flask app factory pattern
Use the application factory pattern so the app can be instantiated with different configs
for testing versus production:

```python
# app.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)

    from routes import bp
    app.register_blueprint(bp)

    @app.route('/health')
    def health():
        return {"status": "ok"}, 200

    return app

app = create_app()
```

### docker-compose.yml pattern per service
Each service gets its own isolated PostgreSQL container. Never share a database between
two services — this defeats the purpose of the microservice architecture.

```yaml
user-service:
  build: ./services/user-service
  ports:
    - "3001:5000"
  environment:
    DATABASE_URL: postgresql://postgres:password@user-db:5432/users
  depends_on:
    user-db:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
    interval: 10s
    timeout: 5s
    retries: 5

user-db:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: users
    POSTGRES_PASSWORD: password
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres"]
    interval: 5s
    timeout: 5s
    retries: 5
```

### Standard error response shape
All services and orchestrators must return errors in the same envelope:

```python
def error_response(code, message, status_code):
    return {"success": False, "error": {"code": code, "message": message}}, status_code

def success_response(data, status_code=200):
    return {"success": True, "data": data}, status_code
```

### Environment variables
Define all keys in .env.example at the root from day one. Each service only references
its own variables. Never share a single .env file across services.

---

## Phase 1 — Foundation Services

These five services (User, Venue, Seat, Credit, Credit Transaction) have no outbound
calls to other services. They only talk to their own PostgreSQL database. Build them first.

### Build each service in this pattern:
1. Scaffold the folder structure
2. Write the SQLAlchemy model in models.py
3. Run migrations: flask db init -> flask db migrate -m "initial" -> flask db upgrade
4. Implement each route in routes.py
5. Test each endpoint manually with Postman
6. Add to docker-compose.yml and verify it boots cleanly

### SQLAlchemy model pattern
Use UUIDs as primary keys. Generate them in Python so tests never depend on the database
for ID creation:

```python
# models.py
from app import db
import uuid
from datetime import datetime

class User(db.Model):
    __tablename__ = 'users'
    userId      = db.Column(db.String(36), primary_key=True,
                            default=lambda: str(uuid.uuid4()))
    email       = db.Column(db.String(255), unique=True, nullable=False)
    password    = db.Column(db.String(255), nullable=False)
    salt        = db.Column(db.String(255), nullable=False)
    phoneNumber = db.Column(db.String(20), nullable=False)
    role        = db.Column(db.String(20), nullable=False, default='user')
    isFlagged   = db.Column(db.Boolean, nullable=False, default=False)
    createdAt   = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
```

### Route handler pattern
Keep route handlers thin. Validate input, call a function, return a response. Never put
business logic directly in a route handler:

```python
# routes.py
from flask import Blueprint, request, jsonify
from models import User, db

bp = Blueprint('users', __name__)

@bp.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    required = ['email', 'password', 'salt', 'phoneNumber']
    if not data or not all(k in data for k in required):
        return jsonify({"error": {"code": "VALIDATION_ERROR",
                                  "message": "Missing required fields"}}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": {"code": "EMAIL_ALREADY_EXISTS",
                                  "message": "Email already registered"}}), 409

    user = User(
        email=data['email'],
        password=data['password'],
        salt=data['salt'],
        phoneNumber=data['phoneNumber']
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({
        "userId": user.userId,
        "email": user.email,
        "role": user.role,
        "createdAt": user.createdAt.isoformat()
    }), 201
```

### Key notes per service

**User Service — password handling**
The User Service stores exactly what it receives — a pre-hashed password and salt. All
bcrypt logic lives in the Auth Orchestrator. Add bcrypt to the Auth Orchestrator's
requirements.txt, not here.

**Credit Service — OutSystems, not Flask**
The Credit Service is built and hosted in OutSystems, not as a Flask service. Do not
scaffold a Flask service or create a Postgres container for it. Instead, the OutSystems
team builds three REST endpoints that expose the same contract as the API reference PDF.
Your only responsibilities here are to verify the endpoints work correctly via Postman,
confirm the JSON response shapes match what your orchestrators expect, and add
`CREDIT_SERVICE_URL` and `OUTSYSTEMS_API_KEY` to `.env.example`.

Since OutSystems is external to your Docker network, all calls to it go over HTTPS.
Create a dedicated helper in any orchestrator that touches Credit Service so the API
key header is always injected consistently:

```python
def call_credit_service(method, path, **kwargs):
    headers = kwargs.pop('headers', {})
    headers['X-API-Key'] = os.environ['OUTSYSTEMS_API_KEY']
    return call_service(
        method,
        f"{os.environ['CREDIT_SERVICE_URL']}{path}",
        headers=headers,
        **kwargs
    )
```

Use `call_credit_service()` everywhere instead of the generic `call_service()` when
calling credit endpoints. This keeps the API key injection in one place.

**One thing to confirm with the OutSystems team before building orchestrators:**
The PATCH /credits/<user_id> response must include the updated `creditBalance` in the
response body. If it does not, your orchestrators will need an extra GET call after
every balance update to confirm the new value. Aligning on this early saves rework.

**Venue and Seat Services — seed data early**
Seed at least 2 venues and their full seat rows during Phase 1. You will need this data
in Phase 2. Add a seed.py script to each service and run it via docker compose exec:

```python
# seed.py
from app import create_app
from models import Venue, db

app = create_app()
with app.app_context():
    db.session.add(Venue(
        venueId='ven_001',
        name='Esplanade Concert Hall',
        capacity=1800,
        address='1 Esplanade Dr',
        postalCode='038981',
        coordinates='1.2897,103.8555',
        isActive=True
    ))
    db.session.commit()
    print("Seeded venues")
```

---

## Phase 2 — Event & Seat Inventory Services

### Event Service
The Event Service only creates the event record. It does not create seat inventory —
that is triggered separately after the event is created. Keep the Event Service dumb.
Seed at least 2 events pointing to your seeded venues.

### Seat Inventory Service — most critical service in the system
This service is the most technically demanding because it uses both REST and gRPC and
handles pessimistic locking under concurrent requests.

Additional requirements:

```
grpcio==1.64.0
grpcio-tools==1.64.0
```

**The .proto file**
Define the proto file at the repo root under proto/seat_inventory.proto. Both the server
and every gRPC client must use the same generated stubs. Commit the generated files:

```protobuf
syntax = "proto3";

service SeatInventoryService {
  rpc HoldSeat      (HoldSeatRequest)      returns (HoldSeatResponse);
  rpc ReleaseSeat   (ReleaseSeatRequest)   returns (ReleaseSeatResponse);
  rpc SellSeat      (SellSeatRequest)      returns (SellSeatResponse);
  rpc GetSeatStatus (GetSeatStatusRequest) returns (GetSeatStatusResponse);
}

message HoldSeatRequest {
  string inventory_id          = 1;
  string user_id               = 2;
  int32  hold_duration_seconds = 3;
}
message HoldSeatResponse {
  bool   success    = 1;
  string status     = 2;
  string held_until = 3;
  string error_code = 4;
}
message ReleaseSeatRequest  { string inventory_id = 1; }
message ReleaseSeatResponse { bool success = 1; }
message SellSeatRequest     { string inventory_id = 1; }
message SellSeatResponse    { bool success = 1; }
message GetSeatStatusRequest  { string inventory_id = 1; }
message GetSeatStatusResponse {
  string inventory_id = 1;
  string status       = 2;
  string held_until   = 3;
}
```

Generate Python stubs from the repo root:

```bash
python -m grpc_tools.protoc \
  -I./proto \
  --python_out=./services/seat-inventory-service \
  --grpc_python_out=./services/seat-inventory-service \
  ./proto/seat_inventory.proto
```

Copy the generated seat_inventory_pb2.py and seat_inventory_pb2_grpc.py into each
orchestrator that calls this service.

**Pessimistic locking with SQLAlchemy**
Use with_for_update() to lock the row so two simultaneous requests cannot both succeed:

```python
from sqlalchemy import select
from models import SeatInventory, db
from datetime import datetime, timedelta

def hold_seat(inventory_id, user_id, hold_duration_seconds):
    with db.session.begin():
        seat = db.session.execute(
            select(SeatInventory)
            .where(SeatInventory.inventoryId == inventory_id)
            .with_for_update()      # row-level lock
        ).scalar_one_or_none()

        if seat is None:
            return None, 'SEAT_NOT_FOUND'
        if seat.status != 'available':
            return None, 'SEAT_NOT_AVAILABLE'

        seat.status = 'held'
        seat.heldUntil = datetime.utcnow() + timedelta(seconds=hold_duration_seconds)
        return seat, None
```

The second concurrent request blocks at with_for_update() until the first commits.
If the first set the seat to held, the second finds status != 'available' and returns
SEAT_NOT_AVAILABLE. This is correct behaviour.

**Running both REST and gRPC servers**
Use Python's threading module to run both servers in parallel:

```python
# server.py
import threading
import grpc
from concurrent import futures
from app import create_app
from grpc_server import SeatInventoryServicer
import seat_inventory_pb2_grpc

def start_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    seat_inventory_pb2_grpc.add_SeatInventoryServiceServicer_to_server(
        SeatInventoryServicer(), server
    )
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()

grpc_thread = threading.Thread(target=start_grpc, daemon=True)
grpc_thread.start()

flask_app = create_app()
flask_app.run(host='0.0.0.0', port=5000)
```

**Test concurrent holds explicitly**
Write a test that fires two simultaneous HoldSeat requests for the same seat using
Python's threading module. Assert exactly one succeeds and one returns SEAT_NOT_AVAILABLE.

---

## Phase 3 — Ticket, Marketplace & Transfer Services

Build in this order: Ticket -> Ticket Log -> Marketplace -> Transfer.

**Ticket Service — QR hash generation**
The QR hash is generated by the QR Orchestrator, not here. The Ticket Service stores
whatever hash and timestamp the orchestrator sends via PATCH /tickets/:ticketId.

**Transfer Service — state store only**
The Transfer Service does not enforce or validate status transitions. The Transfer
Orchestrator is responsible for calling it with the correct status at each step. Never
add transition validation logic to the Transfer Service.

---

## Phase 4 — External Wrappers

### Stripe Wrapper
Additional requirements:

```
stripe==9.9.0
```

**Development setup:**
1. Create a free Stripe test account
2. Copy your test secret key (sk_test_...) into .env
3. Run: stripe listen --forward-to localhost:PORT/stripe/webhook
4. Add the webhook signing secret output by the CLI to .env as STRIPE_WEBHOOK_SECRET

**Creating a Payment Intent — attach userId in metadata:**

```python
import stripe, os
stripe.api_key = os.environ['STRIPE_SECRET_KEY']

def create_payment_intent(user_id, amount_credits):
    intent = stripe.PaymentIntent.create(
        amount=amount_credits * 100,    # Stripe uses smallest currency unit (cents)
        currency='sgd',
        metadata={'userId': user_id}
    )
    return intent.client_secret, intent.id
```

**Webhook verification — never skip this:**

```python
@bp.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():
    payload   = request.get_data()
    signature = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, os.environ['STRIPE_WEBHOOK_SECRET']
        )
    except stripe.error.SignatureVerificationError:
        return {"error": "Invalid signature"}, 400

    if event['type'] == 'payment_intent.succeeded':
        intent  = event['data']['object']
        user_id = intent['metadata']['userId']
        credits = intent['amount'] // 100
        # forward result to Credit Orchestrator
    return {}, 200
```

### OTP Wrapper
Keep this thin — two methods only: send (returns SID) and verify (returns True/False).
This service stores nothing:

```python
import requests, os

SMU_API_BASE = os.environ['SMU_API_BASE_URL']

def send_otp(phone_number):
    response = requests.post(f"{SMU_API_BASE}/send", json={"phone": phone_number})
    response.raise_for_status()
    return response.json()['sid']

def verify_otp(sid, otp):
    response = requests.post(f"{SMU_API_BASE}/verify", json={"sid": sid, "otp": otp})
    response.raise_for_status()
    return response.json()['valid']
```

---

## Phase 5 — RabbitMQ Setup

Add to docker-compose.yml using the management image — the UI at port 15672 is very
useful for debugging queues during development:

```yaml
rabbitmq:
  image: rabbitmq:3-management
  ports:
    - "5672:5672"
    - "15672:15672"
  environment:
    RABBITMQ_DEFAULT_USER: guest
    RABBITMQ_DEFAULT_PASS: guest
  healthcheck:
    test: ["CMD", "rabbitmq-diagnostics", "ping"]
    interval: 10s
    timeout: 5s
    retries: 5
```

Additional requirements for any service using RabbitMQ:

```
pika==1.3.2
```

**Seat Hold TTL Queue with Dead Letter Exchange:**

```python
import pika, os, json

def setup_queues():
    connection = pika.BlockingConnection(
        pika.URLParameters(os.environ['RABBITMQ_URL'])
    )
    channel = connection.channel()

    # DLX exchange and dead letter queue
    channel.exchange_declare(exchange='seat-hold-dlx',
                             exchange_type='direct', durable=True)
    channel.queue_declare(queue='seat-hold-expired', durable=True)
    channel.queue_bind(queue='seat-hold-expired',
                       exchange='seat-hold-dlx', routing_key='expired')

    # TTL queue — dead letters route to DLX
    channel.queue_declare(queue='seat-hold-ttl', durable=True, arguments={
        'x-dead-letter-exchange': 'seat-hold-dlx',
        'x-dead-letter-routing-key': 'expired'
    })
    connection.close()

def publish_hold_expiry(inventory_id, hold_duration_ms):
    connection = pika.BlockingConnection(
        pika.URLParameters(os.environ['RABBITMQ_URL'])
    )
    channel = connection.channel()
    channel.basic_publish(
        exchange='',
        routing_key='seat-hold-ttl',
        body=json.dumps({'inventoryId': inventory_id}),
        properties=pika.BasicProperties(
            expiration=str(hold_duration_ms),
            delivery_mode=2     # persistent
        )
    )
    connection.close()
```

**DLX consumer (run as background thread in Ticket Purchase Orchestrator):**

```python
def start_dlx_consumer():
    connection = pika.BlockingConnection(
        pika.URLParameters(os.environ['RABBITMQ_URL'])
    )
    channel = connection.channel()

    def on_expired(ch, method, properties, body):
        data = json.loads(body)
        release_seat_grpc(data['inventoryId'])   # call Seat Inventory gRPC
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue='seat-hold-expired',
                          on_message_callback=on_expired)
    channel.start_consuming()   # blocks — run in a thread
```

---

## Phase 6 — Orchestrators

Orchestrators are Flask services that make outbound HTTP calls to atomic services
instead of talking to a database. Add requests to every orchestrator's requirements:

```
requests==2.32.3
PyJWT==2.8.0
bcrypt==4.1.3
```

### Internal service call helper
Centralise outbound calls in a helper that handles timeouts and errors consistently:

```python
import requests, os

def call_service(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=5, **kwargs)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.Timeout:
        return None, 'SERVICE_TIMEOUT'
    except requests.exceptions.HTTPError as e:
        return None, e.response.json().get('error', {}).get('code', 'SERVICE_ERROR')
```

### JWT middleware
Build once in the Auth Orchestrator and copy to every orchestrator that needs auth:

```python
import jwt, os
from functools import wraps
from flask import request, jsonify

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({"error": {"code": "UNAUTHORIZED",
                                      "message": "Missing token"}}), 401
        try:
            payload = jwt.decode(token, os.environ['JWT_SECRET'], algorithms=['HS256'])
            request.user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"error": {"code": "TOKEN_EXPIRED",
                                      "message": "Token has expired"}}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": {"code": "UNAUTHORIZED",
                                      "message": "Invalid token"}}), 401
        return f(*args, **kwargs)
    return decorated

def require_staff(f):
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if request.user.get('role') not in ('staff', 'admin'):
            return jsonify({"error": {"code": "NOT_STAFF",
                                      "message": "Staff access required"}}), 403
        return f(*args, **kwargs)
    return decorated
```

### 6.1 Auth Orchestrator — build this first
Establishes the JWT pattern all other orchestrators reuse. Get this solid first.

**Registration — compensate if credit init fails:**

```python
@bp.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    salt   = bcrypt.gensalt()
    hashed = bcrypt.hashpw(data['password'].encode(), salt).decode()

    user_data, err = call_service('POST', f"{USER_SERVICE}/users", json={
        'email': data['email'], 'password': hashed,
        'salt': salt.decode(), 'phoneNumber': data['phoneNumber']
    })
    if err:
        return jsonify({"error": {"code": err}}), 400

    # Initialise credit balance in OutSystems
    _, credit_err = call_credit_service('POST', f"/credits",
                                        json={'userId': user_data['userId']})
    if credit_err:
        # compensating action — remove the user we just created
        call_service('DELETE', f"{USER_SERVICE}/users/{user_data['userId']}")
        return jsonify({"error": {"code": "REGISTRATION_FAILED"}}), 500

    return jsonify({"success": True, "data": user_data}), 201
```

**JWT payload — include venueId for staff users:**
The Ticket Verification Orchestrator reads venueId directly from the JWT to prevent
spoofing. Set it at login time for staff accounts:

```python
def generate_token(user, venue_id=None):
    payload = {
        'userId': user['userId'],
        'email': user['email'],
        'role': user['role'],
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    if venue_id:
        payload['venueId'] = venue_id
    return jwt.encode(payload, os.environ['JWT_SECRET'], algorithm='HS256')
```

### 6.2 Event Orchestrator — build this second
The only fully public orchestrator — no JWT middleware. It is read-only and a good smoke
test that internal HTTP calls between services are working correctly.

### 6.3 Credit Orchestrator
The Stripe webhook endpoint must not use @require_auth — it is called by Stripe, not
your frontend. Verify the Stripe signature instead (see Phase 4).

**Calling OutSystems for balance updates:**
Use `call_credit_service()` for all Credit Service calls. This helper wraps the generic
`call_service()` and always injects the OutSystems API key header:

```python
def call_credit_service(method, path, **kwargs):
    headers = kwargs.pop('headers', {})
    headers['X-API-Key'] = os.environ['OUTSYSTEMS_API_KEY']
    return call_service(
        method,
        f"{os.environ['CREDIT_SERVICE_URL']}{path}",
        headers=headers,
        **kwargs
    )
```

The full webhook flow once Stripe confirms payment:

```python
# 1. Check idempotency — has this payment intent already been processed?
existing, _ = call_service('GET',
    f"{CREDIT_TXN_SERVICE}/credit-transactions/reference/{payment_intent_id}")
if existing:
    return jsonify({"success": True}), 200   # already processed, do nothing

# 2. Get current balance from OutSystems
credit_data, _ = call_credit_service('GET', f"/credits/{user_id}")
current_balance = credit_data['creditBalance']

# 3. Update balance in OutSystems (absolute value)
call_credit_service('PATCH', f"/credits/{user_id}",
    json={'creditBalance': current_balance + credits})

# 4. Log to Credit Transaction Service
call_service('POST', f"{CREDIT_TXN_SERVICE}/credit-transactions", json={
    'userId': user_id,
    'delta': credits,
    'reason': 'topup',
    'referenceId': payment_intent_id
})
```

**Idempotency — prevent double crediting:**
Stripe may deliver the same webhook more than once. The idempotency check in step 1
above guards against this — always perform it before any balance update.

### 6.4 Ticket Purchase Orchestrator
Set up the gRPC client using the generated stubs:

```python
import grpc
import seat_inventory_pb2
import seat_inventory_pb2_grpc
import os

_channel = grpc.insecure_channel(os.environ['SEAT_INVENTORY_GRPC_URL'])
_stub    = seat_inventory_pb2_grpc.SeatInventoryServiceStub(_channel)

def hold_seat_grpc(inventory_id, user_id, duration_seconds):
    req = seat_inventory_pb2.HoldSeatRequest(
        inventory_id=inventory_id,
        user_id=user_id,
        hold_duration_seconds=duration_seconds
    )
    return _stub.HoldSeat(req)
```

Start the DLX consumer as a background thread when the orchestrator starts:

```python
# inside create_app()
import threading
from dlx_consumer import start_dlx_consumer

t = threading.Thread(target=start_dlx_consumer, daemon=True)
t.start()
```

**Credit check against OutSystems:**
When confirming a purchase, fetch the buyer's balance from OutSystems using
`call_credit_service()` before deducting. After a successful purchase, update the
balance in OutSystems with the new absolute value and then log the movement to your
Credit Transaction Service:

```python
# Check balance
credit_data, _ = call_credit_service('GET', f"/credits/{user_id}")
if credit_data['creditBalance'] < ticket_price:
    return jsonify({"error": {"code": "INSUFFICIENT_CREDITS"}}), 402

# Deduct in OutSystems
call_credit_service('PATCH', f"/credits/{user_id}",
    json={'creditBalance': credit_data['creditBalance'] - ticket_price})

# Log to Credit Transaction Service
call_service('POST', f"{CREDIT_TXN_SERVICE}/credit-transactions", json={
    'userId': user_id,
    'delta': -ticket_price,
    'reason': 'ticket_purchase',
    'referenceId': ticket_id
})
```

Never hardcode the hold duration — use an environment variable so it can be set to
10 seconds in test and 10 minutes in production:

```bash
SEAT_HOLD_DURATION_SECONDS=600   # production
SEAT_HOLD_DURATION_SECONDS=10    # test
```


### 6.5 QR Orchestrator
The QR_SECRET must be a long random string (32+ characters) stored as an environment
variable — never hardcode it. Generate one with: python -c "import secrets; print(secrets.token_hex(32))"

```python
import hashlib, os
from datetime import datetime

def generate_qr_hash(ticket_id):
    timestamp = datetime.utcnow().isoformat()
    raw = f"{ticket_id}|{timestamp}|{os.environ['QR_SECRET']}"
    return hashlib.sha256(raw.encode()).hexdigest(), timestamp
```

The 60-second TTL is enforced at scan time by the Ticket Verification Orchestrator.
The QR Orchestrator only generates and stores the hash.

### 6.6 Marketplace Orchestrator
Before creating a listing, check the ticket status is exactly 'active'. Reject anything
in pending_transfer, listed, used, or expired state:

```python
if ticket['status'] != 'active':
    return jsonify({"error": {"code": "TICKET_NOT_ELIGIBLE",
                              "message": "Ticket cannot be listed in its current state"}}), 400
```

### 6.7 Transfer Orchestrator — most complex in the system
Build this last among the orchestrators. It has the most steps and requires compensating
logic if anything fails mid-transfer.

**Atomicity of the final transfer step — saga pattern:**
Since the transfer touches six separate atomic services, a database transaction is not
available. Compensate in reverse order if any step fails:

```python
def execute_transfer(transfer_id, buyer_id, seller_id,
                     credit_amount, ticket_id, listing_id,
                     buyer_balance, seller_balance):
    completed = []
    try:
        # Steps 1-2: update balances in OutSystems
        call_credit_service('PATCH', f"/credits/{buyer_id}",
                     json={'creditBalance': buyer_balance - credit_amount})
        completed.append('buyer_deducted')

        # Step 2: credit seller in OutSystems
        call_credit_service('PATCH', f"/credits/{seller_id}",
                     json={'creditBalance': seller_balance + credit_amount})
        completed.append('seller_credited')

        # Step 3-4: log both movements to your Credit Transaction Service
        call_service('POST', f"{CREDIT_TXN_SERVICE}/credit-transactions",
                     json={'userId': buyer_id, 'delta': -credit_amount,
                           'reason': 'p2p_sent', 'referenceId': transfer_id})
        completed.append('buyer_txn_logged')

        call_service('POST', f"{CREDIT_TXN_SERVICE}/credit-transactions",
                     json={'userId': seller_id, 'delta': credit_amount,
                           'reason': 'p2p_received', 'referenceId': transfer_id})
        completed.append('seller_txn_logged')

        # Steps 5-7: update ticket, listing, and transfer state
        call_service('PATCH', f"{TICKET_SERVICE}/tickets/{ticket_id}",
                     json={'ownerId': buyer_id, 'status': 'active'})
        completed.append('ticket_transferred')

        call_service('PATCH', f"{MARKETPLACE_SERVICE}/listings/{listing_id}",
                     json={'status': 'completed'})

        call_service('PATCH', f"{TRANSFER_SERVICE}/transfers/{transfer_id}",
                     json={'status': 'completed',
                           'completedAt': datetime.utcnow().isoformat()})

    except Exception as e:
        # compensate in reverse order — restore OutSystems balances
        if 'seller_credited' in completed:
            call_credit_service('PATCH', f"/credits/{seller_id}",
                         json={'creditBalance': seller_balance})
        if 'buyer_deducted' in completed:
            call_credit_service('PATCH', f"/credits/{buyer_id}",
                         json={'creditBalance': buyer_balance})
        call_service('PATCH', f"{TRANSFER_SERVICE}/transfers/{transfer_id}",
                     json={'status': 'failed'})
        raise e
```

**Re-check buyer credits at execution time:**
The buyer's balance was checked at initiation. They may have spent credits since then.
Always re-fetch from OutSystems immediately before deducting:

```python
buyer_credit, _ = call_credit_service('GET', f"/credits/{buyer_id}")
if buyer_credit['creditBalance'] < credit_amount:
    return jsonify({"error": {"code": "INSUFFICIENT_CREDITS"}}), 402
```

**Prevent double execution:**
Before executing, assert status is still pending_seller_otp and sellerOtpVerified is False:

```python
if transfer['status'] != 'pending_seller_otp' or transfer['sellerOtpVerified']:
    return jsonify({"error": {"code": "WRONG_TRANSFER_STATUS"}}), 400
```

### 6.8 Ticket Verification Orchestrator
The staff's venueId must come from the JWT — never from the request body. If the
frontend could pass it, a malicious staff member could verify tickets at any venue.

**Check order — perform in this exact sequence:**
1. Look up ticket by QR hash
2. Check QR TTL (60 seconds) — log 'expired' if stale
3. Validate event is active
4. Confirm seat status is sold
5. Confirm ticket status is active
6. Check for duplicate scan — log 'duplicate' if already checked in
7. Check venue match — log 'wrong_venue' and return redirect if mismatch
8. All pass: update ticket to 'used', log 'checked_in'

Putting venue match last ensures expired or used tickets return the correct error rather
than a confusing venue redirect.

The venueId for the staff member is read from the JWT:

```python
@bp.route('/verify/scan', methods=['POST'])
@require_staff
def scan_ticket():
    qr_hash        = request.get_json().get('qrHash')
    staff_venue_id = request.user.get('venueId')   # from JWT, not request body
    # ...
```

---

## Phase 7 — End-to-End Testing

Test each scenario as a complete flow using your Postman collection. Do not
test individual endpoints in isolation here — test the full journey end to end.

**Scenario 2b (hold expiry):**
Set SEAT_HOLD_DURATION_SECONDS=10 in your test environment so you do not wait 10 minutes.
Verify the seat status returns to 'available' automatically after 10 seconds.

**Scenario 3 (P2P transfer):**
Use two separate user accounts. Step through the full flow manually — initiate as buyer,
verify OTP as buyer, accept as seller, verify OTP as seller — and confirm credits and
ticket ownership change correctly at each step.

**Scenario 4 (verification):**
Get a fresh QR hash, immediately scan it (should succeed). Wait 61 seconds and scan
again (should return QR_EXPIRED). Scan the original successful hash again (should
return DUPLICATE_SCAN).

---

## Phase 8 — Docker & Kubernetes

### Docker Compose checklist before Kompose
Ensure your docker-compose.yml:
- Has healthcheck defined for every service and database container
- Uses named volumes for all PostgreSQL containers
- Has all inter-service URLs using Docker service names, not localhost
- Has restart: unless-stopped on all services
- Has SEAT_HOLD_DURATION_SECONDS as an env var, not hardcoded

### After Kompose — manual fixes required

**1. Secrets**
Kompose puts env var values as plaintext in Deployment YAML. Move sensitive values to
Kubernetes Secret objects:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
stringData:
  JWT_SECRET: "your-secret-here"
  STRIPE_SECRET_KEY: "sk_live_..."
  QR_SECRET: "your-qr-secret-here"
  STRIPE_WEBHOOK_SECRET: "whsec_..."
```

Reference in each Deployment:

```yaml
env:
  - name: JWT_SECRET
    valueFrom:
      secretKeyRef:
        name: app-secrets
        key: JWT_SECRET
```

**2. Health check probes**
Add to every Deployment:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 5000
  initialDelaySeconds: 15
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /health
    port: 5000
  initialDelaySeconds: 5
  periodSeconds: 5
```

**3. Resource limits**
Add to every Deployment as a baseline — tune later based on observed usage:

```yaml
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "256Mi"
    cpu: "500m"
```

**4. HorizontalPodAutoscaler**
Add for seat-inventory-service and ticket-purchase-orchestrator:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: seat-inventory-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: seat-inventory-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

**5. Ingress**
Replace NodePort services on orchestrators with ClusterIP and route all external traffic
through a single Ingress resource:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ticketremaster-ingress
spec:
  rules:
    - http:
        paths:
          - path: /auth
            pathType: Prefix
            backend:
              service:
                name: auth-orchestrator
                port:
                  number: 5000
          - path: /events
            pathType: Prefix
            backend:
              service:
                name: event-orchestrator
                port:
                  number: 5000
          - path: /purchase
            pathType: Prefix
            backend:
              service:
                name: ticket-purchase-orchestrator
                port:
                  number: 5000
          - path: /credits
            pathType: Prefix
            backend:
              service:
                name: credit-orchestrator
                port:
                  number: 5000
          - path: /marketplace
            pathType: Prefix
            backend:
              service:
                name: marketplace-orchestrator
                port:
                  number: 5000
          - path: /transfer
            pathType: Prefix
            backend:
              service:
                name: transfer-orchestrator
                port:
                  number: 5000
          - path: /tickets
            pathType: Prefix
            backend:
              service:
                name: qr-orchestrator
                port:
                  number: 5000
          - path: /verify
            pathType: Prefix
            backend:
              service:
                name: ticket-verification-orchestrator
                port:
                  number: 5000
```

### Testing on Minikube

```bash
minikube start
eval $(minikube docker-env)    # point Docker CLI at Minikube's daemon
docker compose build           # build all images into Minikube's daemon
kubectl apply -f k8s/          # apply all manifests
minikube tunnel                # expose Ingress at localhost
```

