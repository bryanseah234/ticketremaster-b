# stripe-wrapper

Stripe wrapper handles payment-intent creation and webhook signature verification for credit top-up flows.

## Endpoints

- `GET /health`
- `POST /stripe/create-payment-intent`
- `POST /stripe/webhook`

## Request and Response Contract

### `POST /stripe/create-payment-intent`
Request body:

```json
{
  "userId": "user-123",
  "amount": 50
}
```

Rules:
- `amount` must be a positive integer
- amount is interpreted in credits and converted to cents for Stripe (`amount * 100`)

Success response:

```json
{
  "clientSecret": "cs_...",
  "paymentIntentId": "pi_...",
  "amount": 50
}
```

### `POST /stripe/webhook`

Input:
- raw request body from Stripe
- `Stripe-Signature` header

Success response shape:

```json
{
  "received": true,
  "userId": "user-123",
  "credits": "50",
  "paymentIntentId": "pi_..."
}
```

Invalid signature response:

```json
{
  "error": {
    "code": "INVALID_SIGNATURE",
    "message": "..."
  }
}
```

## Environment Variables

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`

## Automated Testing

Run wrapper unit tests:

```powershell
docker compose run --rm stripe-wrapper python -m pytest -p no:cacheprovider tests
```

Current automated tests validate:
- payment-intent happy path
- request validation
- webhook signature-rejection behavior
- webhook payload extraction for `payment_intent.succeeded`

## Manual Testing

### 1) Payment intent API check

```powershell
curl -X POST "http://localhost:5011/stripe/create-payment-intent" -H "Content-Type: application/json" -d "{\"userId\":\"user-123\",\"amount\":50}"
```

Expected:
- HTTP 200
- JSON includes `clientSecret` and `paymentIntentId`

### 2) Signature rejection check

```powershell
curl -X POST "http://localhost:5011/stripe/webhook" -H "Content-Type: application/json" -H "Stripe-Signature: invalid" -d "{\"type\":\"payment_intent.succeeded\"}"
```

Expected:
- HTTP 400
- error code `INVALID_SIGNATURE`

### 3) Real webhook verification with Stripe CLI

1. Login to Stripe CLI:

```powershell
stripe login
```

2. Start listener and forward events:

```powershell
stripe listen --forward-to localhost:5011/stripe/webhook
```

3. Copy generated `whsec_...` to `.env` as `STRIPE_WEBHOOK_SECRET`.
4. Recreate wrapper so it reloads env:

```powershell
docker compose up -d --force-recreate stripe-wrapper
```

5. Trigger test event:

```powershell
stripe trigger payment_intent.succeeded
```

Expected:
- Stripe CLI shows successful delivery (HTTP 200)
- Wrapper returns payload with `received: true`

## Related Docs

- Full testing guide: [../../TESTING.md](../../TESTING.md)
- Postman flow: [../../postman/README.md](../../postman/README.md)
- Wrapper implementation source: [routes.py](routes.py)

