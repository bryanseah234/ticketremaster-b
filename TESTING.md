# TicketRemaster Testing Guide

This guide covers local Docker validation, Postman execution, external integration checks, and Kubernetes troubleshooting for the current codebase.

Related references:

- [README.md](README.md)
- [API.md](API.md)
- [FRONTEND.md](FRONTEND.md)
- [OUTSYSTEMS.md](OUTSYSTEMS.md)
- [postman/README.md](postman/README.md)

## 1) Prerequisites

- Docker Desktop running
- Postman desktop app installed
- Stripe CLI installed for valid webhook-path testing
- `kubectl` configured if you want to validate the Kubernetes manifests against a cluster
- a local `.env` file at repo root copied from `.env.example`

Important `.env` values for integration tests:

- `JWT_SECRET`
- `QR_SECRET`
- `CREDIT_SERVICE_URL`
- `OUTSYSTEMS_API_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `SMU_API_URL`
- `SMU_API_KEY`

## 2) Start the local stack

```powershell
docker compose up -d --build
```

Quick smoke checks:

```powershell
docker compose ps
docker compose exec redis redis-cli ping
docker compose exec rabbitmq rabbitmq-diagnostics -q ping
```

Expected:

- all application containers move to healthy
- Redis returns `PONG`
- RabbitMQ diagnostics return success

Local runtime surfaces:

- Kong gateway: `http://localhost:8000`
- Kong admin: `http://localhost:8001`
- RabbitMQ management: `http://localhost:15672`
- Auth Swagger: `http://localhost:8100/apidocs`
- Event Swagger: `http://localhost:8101/apidocs`
- Credit Swagger: `http://localhost:8102/apidocs`

## 3) Run migrations and seed baseline data

The shared Postman environment depends on seeded baseline records.

### Migrations

```powershell
docker compose run --rm user-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm venue-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm seat-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm event-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm seat-inventory-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm ticket-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm ticket-log-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm marketplace-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm transfer-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm credit-transaction-service python -m flask --app app.py db upgrade -d migrations
```

### Seeds

```powershell
docker compose run --rm user-service python user_seed.py
docker compose run --rm venue-service python seed_venues.py
docker compose run --rm seat-service python seed_seats.py
docker compose run --rm event-service python seed_events.py
docker compose run --rm seat-inventory-service python seed_seat_inventory.py
```

Baseline values expected by the shared local environment:

- `user_email=admin1@ticketremaster.local`
- `venue_id=ven_001`
- `event_id=evt_001`

## 4) Import and run the Postman collection

Import:

- `postman/TicketRemaster.postman_collection.json`
- `postman/TicketRemaster.local.postman_environment.json`

Set the active environment to `TicketRemaster Local`.

Important local URLs to confirm in the environment:

- `gateway_url=http://localhost:8000`
- `user_service_url=http://localhost:5000`
- `stripe_wrapper_url=http://localhost:5011`
- `otp_wrapper_url=http://localhost:5012`
- `credit_service_url=<your OutSystems base URL>`

### Recommended collection order

1. `00 Health`
2. `01 User Service`
3. `02 Venue Service`
4. `03 Seat Service`
5. `04 Event Service`
6. `05 Seat Inventory Service`
7. `06 Ticket Service`
8. `07 Ticket Log Service`
9. `08 Marketplace Service`
10. `09 Transfer Service`
11. `10 Credit Transaction Service`
12. `11 Stripe Wrapper`
13. `12 OTP Wrapper`
14. `13 RabbitMQ (Phase 5 Checks)`
15. `14 OutSystems Credit Service (Phase 1.4 External)`

What success looks like:

- health requests return `200`
- create operations return generated IDs
- chained environment variables populate correctly
- purchase and transfer flows reuse values created earlier in the run

### Postman CLI

```powershell
postman collection run .\postman\TicketRemaster.postman_collection.json -e .\postman\TicketRemaster.local.postman_environment.json --reporters cli
```

Stop on first failure:

```powershell
postman collection run .\postman\TicketRemaster.postman_collection.json -e .\postman\TicketRemaster.local.postman_environment.json --bail failure --reporters cli
```

## 5) Core workflow spot checks

### Event discovery

- `GET /venues`
- `GET /events`
- `GET /events/{eventId}`
- `GET /events/{eventId}/seats`

Expected:

- venue lists return active venues
- events are enriched with venue information and `seatsAvailable`
- seat-map responses contain `inventoryId`, `status`, `rowNumber`, `seatNumber`, and `price`

### Purchase flow

1. hold a seat through `POST /purchase/hold/{inventoryId}`
2. confirm purchase through `POST /purchase/confirm/{inventoryId}`
3. verify the ticket appears in `GET /tickets`
4. verify the balance changed through `GET /credits/balance`

Expected:

- hold returns `holdToken` and `heldUntil`
- confirm returns `201` with `ticketId`
- if Redis is available, confirm may use cached hold state
- insufficient balance returns `402 INSUFFICIENT_CREDITS`
- expired holds return `410 PAYMENT_HOLD_EXPIRED`

### Marketplace and transfer flow

1. create a listing with `POST /marketplace/list`
2. browse listings with `GET /marketplace`
3. initiate transfer with `POST /transfer/initiate`
4. accept, verify, and complete the buyer and seller OTP flow

Expected:

- initiate returns `pending_seller_acceptance`
- seller accept moves the transfer to `pending_buyer_otp`
- buyer verify moves the transfer to `pending_seller_otp`
- seller verify completes the credit and ownership saga

### QR and verification flow

1. fetch user tickets with `GET /tickets`
2. generate a fresh QR with `GET /tickets/{ticketId}/qr`
3. validate with `POST /verify/scan` or `POST /verify/manual`

Expected:

- QR response contains a short-lived `qrHash`
- expired QR values return `QR_EXPIRED`
- duplicate check-ins return `409 ALREADY_CHECKED_IN`
- wrong venue checks return `WRONG_HALL`

## 6) External integration validation

### 6.1 Stripe wrapper

#### Create payment intent

Run request:

- `POST /stripe/create-payment-intent`

Expected response:

```json
{
  "clientSecret": "cs_...",
  "paymentIntentId": "pi_...",
  "amount": 50
}
```

#### Invalid signature path

Run the collection request for the invalid signature scenario.

Expected:

- HTTP `400`
- `error.code = INVALID_SIGNATURE`

#### Valid signature path with Stripe CLI

```powershell
stripe login
stripe listen --forward-to localhost:5011/stripe/webhook
```

Copy the generated signing secret into `.env` as `STRIPE_WEBHOOK_SECRET`, then recreate only the Stripe wrapper:

```powershell
docker compose up -d --force-recreate stripe-wrapper
```

Trigger an event:

```powershell
stripe trigger payment_intent.succeeded
```

Expected:

- Stripe CLI reports a successful `200` delivery to `localhost:5011/stripe/webhook`

### 6.2 OTP wrapper

Current upstream mapping:

- `POST /otp/send` -> `POST <SMU_API_URL>/SendOTP`
- `POST /otp/verify` -> `POST <SMU_API_URL>/VerifyOTP`

#### Send OTP

Expected response:

```json
{
  "sid": "..."
}
```

#### Verify OTP

Expected response:

```json
{
  "verified": true
}
```

or:

```json
{
  "verified": false
}
```

#### Bad upstream credentials

Expected:

- `502 OTP_SEND_FAILED` for send failures
- `502 OTP_VERIFY_FAILED` for verify failures

### 6.3 OutSystems credit service

Published docs:

- UI: `https://personal-sdxnmlx3.outsystemscloud.com/CreditService/rest/CreditAPI/`
- Swagger: `https://personal-sdxnmlx3.outsystemscloud.com/CreditService/rest/CreditAPI/swagger.json`

Required headers:

- `X-API-KEY: {{outsystems_api_key}}`
- `Content-Type: application/json`

#### Create credit record

Request:

- `POST {{credit_service_url}}/credits`

Repository caller expectation:

```json
{
  "userId": "outsys_test_user_001"
}
```

Published Swagger request shape:

```json
{
  "userId": "outsys_test_user_001",
  "creditBalance": 0
}
```

Testing guidance:

- validate which request shape the provider currently accepts
- treat the published Swagger as the external contract of record
- treat the repo's `userId`-only registration call as an integration point that must stay aligned with the provider

Expected create response:

- HTTP `200` or `201`
- response includes `userId` and `creditBalance`

#### Fetch credit balance

- `GET {{credit_service_url}}/credits/outsys_test_user_001`

Expected:

- HTTP `200`
- numeric balance field, usually `creditBalance`

#### Update credit balance

- `PATCH {{credit_service_url}}/credits/outsys_test_user_001`

Request:

```json
{
  "creditBalance": 120
}
```

Expected:

- HTTP `200`
- response includes the updated balance

#### Negative key test

Repeat a request with an invalid `X-API-KEY`.

Expected:

- HTTP `401` or `403`

## 7) Kubernetes deployment, monitoring, and troubleshooting

### Render and apply the base

```powershell
kubectl kustomize .\k8s\base
kubectl apply -k .\k8s\base
```

### Check namespace and rollout status

```powershell
kubectl get namespaces
kubectl get pods -n ticketremaster-edge
kubectl get pods -n ticketremaster-core
kubectl get pods -n ticketremaster-data
kubectl rollout status deployment/kong -n ticketremaster-edge
kubectl rollout status deployment/ticket-purchase-orchestrator -n ticketremaster-core
kubectl rollout status statefulset/redis -n ticketremaster-data
kubectl rollout status statefulset/rabbitmq -n ticketremaster-data
```

### Inspect individual workloads

```powershell
kubectl describe pod <pod-name> -n ticketremaster-core
kubectl get svc -n ticketremaster-edge
kubectl get svc -n ticketremaster-core
kubectl get svc -n ticketremaster-data
kubectl get endpoints -n ticketremaster-core
kubectl get jobs -n ticketremaster-core
```

### View logs

```powershell
kubectl logs deployment/kong -n ticketremaster-edge --tail=200
kubectl logs deployment/ticket-purchase-orchestrator -n ticketremaster-core --tail=200
kubectl logs deployment/credit-orchestrator -n ticketremaster-core --tail=200
kubectl logs deployment/transfer-orchestrator -n ticketremaster-core --tail=200
kubectl logs statefulset/rabbitmq -n ticketremaster-data --tail=200
kubectl logs statefulset/redis -n ticketremaster-data --tail=200
```

Follow a live stream:

```powershell
kubectl logs deployment/ticket-purchase-orchestrator -n ticketremaster-core -f
```

### Port-forward for browser and health checks

Kong:

```powershell
kubectl port-forward svc/kong-proxy -n ticketremaster-edge 8000:80
```

RabbitMQ management:

```powershell
kubectl port-forward svc/rabbitmq -n ticketremaster-data 15672:15672
```

Direct orchestrator Swagger check:

```powershell
kubectl port-forward svc/credit-orchestrator -n ticketremaster-core 8102:5000
```

### Verify service health from a developer machine

After port-forwarding Kong:

```powershell
Invoke-RestMethod http://localhost:8000/events
Invoke-RestMethod http://localhost:8000/venues
```

To verify a service health endpoint directly:

```powershell
kubectl port-forward svc/ticket-service -n ticketremaster-core 5004:5000
Invoke-RestMethod http://localhost:5004/health
```

To verify Kong inside the cluster:

```powershell
kubectl exec deployment/kong -n ticketremaster-edge -- kong health
```

### Common kubectl troubleshooting patterns

Restart a deployment:

```powershell
kubectl rollout restart deployment/ticket-purchase-orchestrator -n ticketremaster-core
```

Inspect config pushed into Kong:

```powershell
kubectl get configmap kong-declarative-config -n ticketremaster-edge -o yaml
```

Inspect seed job output:

```powershell
kubectl logs job/<job-name> -n ticketremaster-core
```

## 8) Error handling and log-based debugging

Expected TicketRemaster error envelope:

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Unhandled internal server error.",
    "status": 500,
    "traceId": "f3a6f8ea-....",
    "details": {
      "method": "POST",
      "path": "/stripe/webhook",
      "timestamp": "2026-03-29T12:00:00+00:00",
      "resolution": "Check error.code, request payload, and service logs using traceId."
    }
  }
}
```

If Postman or Postman CLI shows HTML instead of JSON:

```text
JSONError: Unexpected token '<' at 1:1
<!doctype html>
```

that usually means the request hit an unhandled server exception.

Recommended debugging sequence:

1. copy `error.traceId` if present
2. check the service logs
3. match the failing `method` and `path`
4. fix the request payload or service configuration
5. rerun the specific request before rerunning the full suite

Useful log commands:

```powershell
docker compose logs --no-color --tail=200 <service-name>
kubectl logs deployment/<deployment-name> -n ticketremaster-core --tail=200
```

## 9) Reset the local environment

Use this only when you want a full clean slate.

```powershell
docker compose down -v
docker compose up -d --build
```

After a volume reset, rerun the migration and seed commands from sections 3 and 4.
