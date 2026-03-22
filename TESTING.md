# TicketRemaster Testing Guide (Postman + External Integrations)

This guide explains how to import and run the shared Postman tests, plus how to validate external integrations and API keys for:
- **1.4 OutSystems Credit Service**
- **4.1 Stripe Wrapper (with Stripe CLI)**
- **4.2 OTP Wrapper (SMU Notification API)**

## 1) Prerequisites

- Docker Desktop running
- Postman desktop app installed
- Stripe CLI installed (for 4.1 valid webhook signature test)
- A local `.env` file at repo root (copy from `.env.example` and fill real secrets)

Required `.env` keys for external checks:
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `SMU_API_URL`
- `SMU_API_KEY`
- `CREDIT_SERVICE_URL`
- `OUTSYSTEMS_API_KEY`

## 2) Start the stack

From repo root:

```powershell
docker compose up -d --build
```

Quick smoke check:
- Open Postman and run folder **00 Health**
- Correct result: each request returns **200** with body like:

```json
{
  "status": "ok"
}
```

## 3) Import Postman assets correctly

1. In Postman, click **Import**.
2. Import:
   - `postman/TicketRemaster.postman_collection.json`
   - `postman/TicketRemaster.local.postman_environment.json`
3. Set active environment to **TicketRemaster Local**.
4. In environment variables, confirm base URLs match local ports:
   - `user_service_url=http://localhost:5000`
   - `stripe_wrapper_url=http://localhost:5011`
   - `otp_wrapper_url=http://localhost:5012`
   - others as needed from the environment file.

## 3.1) Seed-data baseline used by Postman

The shared local environment assumes seeded baseline data:
- `user_email=admin1@ticketremaster.local`
- `venue_id=ven_001`
- `event_id=evt_001`

Before running the full collection, run migrations and seeds so these references exist:

```powershell
docker compose run --rm user-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm venue-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm seat-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm event-service python -m flask --app app.py db upgrade -d migrations
docker compose run --rm seat-inventory-service python -m flask --app app.py db upgrade -d migrations

docker compose run --rm user-service python seed.py
docker compose run --rm venue-service python seed.py
docker compose run --rm seat-service python seed.py
docker compose run --rm event-service python seed.py
docker compose run --rm seat-inventory-service python seed.py
```

The collection auto-captures `user_id`, `venue_id`, `event_id`, and `inventory_id` from responses at runtime.

## 4) Run the core collection in dependency order

Run folders top-to-bottom so IDs are captured into environment variables.

Recommended order:
1. `00 Health`
2. `01 User Service` (sets `user_id`)
3. `02 Venue Service`
4. `03 Seat Service`
5. `04 Event Service` (sets `event_id`)
6. `05 Seat Inventory Service`
7. `06 Ticket Service` (sets `ticket_id`, `ticket_qr_hash`)
8. `07 Ticket Log Service`
9. `08 Marketplace Service` (sets `listing_id`)
10. `09 Transfer Service` (sets `transfer_id`)
11. `10 Credit Transaction Service`
12. `11 Stripe Wrapper`
13. `12 OTP Wrapper`
14. `13 RabbitMQ (Phase 5 Checks)`
15. `14 OutSystems Credit Service (Phase 1.4 External)`

What “correct” looks like:
- Most create/update calls return **200/201** and a JSON object containing a generated ID (`userId`, `eventId`, `ticketId`, `listingId`, `transferId`, etc.).
- GET-by-ID calls return **200** and the same ID you just created.
- Request chaining works when environment values are populated after prior requests.

### Run with Postman CLI (recommended for repeatable checks)

From repo root:

```powershell
postman collection run .\postman\TicketRemaster.postman_collection.json -e .\postman\TicketRemaster.local.postman_environment.json --reporters cli
```

If you want to stop on first failure:

```powershell
postman collection run .\postman\TicketRemaster.postman_collection.json -e .\postman\TicketRemaster.local.postman_environment.json --bail failure --reporters cli
```

## 5) External service validation

## 5.1 Phase 4.1 Stripe Wrapper (including Stripe CLI)

### A) Verify Stripe API key works (Payment Intent creation)
Run request: **11 Stripe Wrapper → Create Payment Intent**

Expected success:
- HTTP **200**
- JSON includes:

```json
{
  "clientSecret": "cs_...",
  "paymentIntentId": "pi_...",
  "amount": 50
}
```

If key/config is wrong, this request fails (typically 4xx/5xx from Stripe wrapper).

### B) Verify signature rejection path
Run request: **11 Stripe Wrapper → Webhook Invalid Signature Check**

Expected:
- HTTP **400**
- JSON contains:

```json
{
  "error": {
    "code": "INVALID_SIGNATURE"
  }
}
```

### C) Verify valid webhook signature path using Stripe CLI
1. In terminal, login and listen:

```powershell
stripe login
stripe listen --forward-to localhost:5011/stripe/webhook
```

2. Copy the generated `whsec_...` signing secret into `.env` as `STRIPE_WEBHOOK_SECRET`.
3. Restart only Stripe wrapper so it reloads env:

```powershell
docker compose up -d --force-recreate stripe-wrapper
```

4. In a second terminal, trigger a test webhook:

```powershell
stripe trigger payment_intent.succeeded
```

Expected:
- Stripe CLI shows event delivered to `localhost:5011/stripe/webhook` with **200**.
- This confirms webhook signature verification path is working with your configured secret.

## 5.2 Phase 4.2 OTP Wrapper (SMU Notification API key check)

SMU Notification endpoints are POST-only. Opening endpoint URLs directly in a browser sends GET and returns:

```json
{"Message":"The requested resource does not support http method 'GET'."}
```

That response is expected for browser checks and does not indicate wrapper failure.

### A) Send OTP
Run request: **12 OTP Wrapper → Send OTP**

Expected success:
- HTTP **200**
- JSON:

```json
{
  "sid": "..."
}
```

Copy returned `sid` into environment variable `otp_sid` (unless already set manually by your team workflow).

### B) Verify OTP
Run request: **12 OTP Wrapper → Verify OTP**

Expected success format:
- HTTP **200**
- JSON:

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

Both are valid API responses; `true/false` depends on the OTP entered.

### C) Detect bad API key / upstream issues
If `SMU_API_KEY` or `SMU_API_URL` is wrong, expected wrapper behavior:
- HTTP **502**
- Error code:
  - `OTP_SEND_FAILED` for `/otp/send`
  - `OTP_VERIFY_FAILED` for `/otp/verify`

OTP wrapper → SMU mapping used by this repo:
- `/otp/send` calls `POST <SMU_API_URL>/SendOTP` with body `{ "Mobile": "<phoneNumber>" }`
- `/otp/verify` calls `POST <SMU_API_URL>/VerifyOTP` with body `{ "VerificationSid": "<sid>", "Code": "<otp>" }`

## 5.3 Phase 1.4 OutSystems Credit Service (external, included in shared Postman collection)

The shared collection already includes folder **14 OutSystems Credit Service (Phase 1.4 External)**.

Before testing, add environment variables:
- `credit_service_url` = your OutSystems base URL (same value as `.env` `CREDIT_SERVICE_URL`)
- `outsystems_api_key` = your OutSystems key (same value as `.env` `OUTSYSTEMS_API_KEY`)

Headers already configured in collection:
- `X-API-Key: {{outsystems_api_key}}`
- `Content-Type: application/json`

### A) Create credit record
- Method/URL: `POST {{credit_service_url}}/credits`
- Body:

```json
{
  "userId": "outsys_test_user_001"
}
```

Expected:
- HTTP **200/201**
- Response includes `userId` and `creditBalance` initialized to `0` (or `0.0`).

### B) Fetch credit balance
- Method/URL: `GET {{credit_service_url}}/credits/outsys_test_user_001`

Expected:
- HTTP **200**
- Response includes `userId` and numeric `creditBalance`.

### C) Update credit balance (absolute value)
- Method/URL: `PATCH {{credit_service_url}}/credits/outsys_test_user_001`
- Body:

```json
{
  "creditBalance": 120
}
```

Expected:
- HTTP **200**
- Response includes updated `creditBalance` in body (this is required for orchestrator compatibility).

### D) API key negative test
Repeat one request with an invalid `X-API-Key`.

Expected:
- HTTP **401/403** (provider-specific)
- Request must be rejected.

## 6) Team validation checklist

Use this pass/fail checklist during walkthrough:
- [ ] All services in **00 Health** return 200 + `{ "status": "ok" }`
- [ ] Core collection runs in order without missing environment IDs
- [ ] Stripe create-payment-intent returns `clientSecret` + `paymentIntentId`
- [ ] Stripe invalid signature request returns `INVALID_SIGNATURE`
- [ ] Stripe CLI forwarded webhook returns HTTP 200
- [ ] OTP send returns `sid`
- [ ] OTP verify returns boolean `verified`
- [ ] OTP invalid key path returns 502 with wrapper error code
- [ ] OutSystems POST/GET/PATCH all succeed with valid key
- [ ] OutSystems rejects invalid key

## 7) Optional clean reset (if state gets messy)

```powershell
docker compose down -v
docker compose up -d --build
```

Use reset only when you intentionally want a fresh database state.

## 8) Troubleshooting JSONError / HTML 500 responses

Symptom seen in Postman or Postman CLI:

```text
JSONError: Unexpected token '<' at 1:1
<!doctype html>
```

This means the endpoint returned HTML instead of JSON, usually from an unhandled server exception.

Expected error format from TicketRemaster services:

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
      "timestamp": "2026-03-21T...",
      "resolution": "Check error.code, request payload, and service logs using traceId.",
      "exceptionType": "ValueError",
      "exceptionMessage": "...",
      "stackTrace": ["Traceback ..."]
    }
  }
}
```

When a request fails:
- Copy `error.traceId`.
- Check service logs:

```powershell
docker compose logs --no-color --tail=200 <service-name>
```

- Match the failing route using `details.path` and `details.method`.
- Apply `details.resolution`, then re-run the specific folder/request before running the full collection.
