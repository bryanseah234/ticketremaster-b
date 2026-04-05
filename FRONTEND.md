# TicketRemaster Frontend Integration Contract

This document is the frontend-facing source of truth for the API surface that is actually reachable through the current gateway configuration.

Related references:

- [README.md](README.md)
- [API.md](API.md)
- [PRD.md](PRD.md)

![Frontend gateway flow](diagrams/frontend_gateway_flow.svg)

<details>
<summary>Mermaid source</summary>

```mermaid
flowchart LR
    FE[Frontend App or Staff App] --> Kong[Kong Gateway]
    Kong --> Auth[auth-orchestrator]
    Kong --> Event[event-orchestrator]
    Kong --> Credit[credit-orchestrator]
    Kong --> Purchase[ticket-purchase-orchestrator]
    Kong --> QR[qr-orchestrator]
    Kong --> Market[marketplace-orchestrator]
    Kong --> Transfer[transfer-orchestrator]
    Kong --> Verify[ticket-verification-orchestrator]
```

</details>

## Quick Start

1. Set frontend API base URL to Kong (`http://localhost:8000` locally, production host in this file).
2. Attach `Authorization` and `apikey` headers according to the matrix below.
3. Send `Idempotency-Key` on top-up, purchase, and transfer state-changing requests.
4. Validate route behavior against [API.md](API.md) before release.

## Base URLs

### Production

- Frontend origin: `https://ticketremaster.hong-yi.me`
- Browser API base URL: `https://ticketremasterapi.hong-yi.me`

### Local development

- Browser API base URL: `http://localhost:8000`
- Use Kong locally as well so the frontend exercises the same route model as production
- Direct orchestrator ports such as `http://localhost:8102` are for Swagger and debugging, not for normal browser integration

### Local gateway key

The declarative Kong config currently defines a local frontend consumer key:

- header: `apikey`
- local development value: `tk_front_123456789`

Treat this as a local or controlled-environment gateway detail. Do not hardcode it into production frontend builds.

## Request rules

- call Kong only
- send `Authorization: Bearer <jwt>` on JWT-protected routes
- send `apikey: <value>` on every route group that Kong key-auth protects
- send `Idempotency-Key: <uuid>` on state-changing operations (top-up, purchase, transfer) to prevent duplicates
- do not call internal services, Docker hostnames, or Kubernetes service DNS names from the browser
- implement exponential backoff for retries on `429`, `503`, `408`, `504` responses

## Authentication matrix

| Route or route group | JWT required | Kong `apikey` required | Idempotency Key | Notes |
| --- | --- | --- | --- | --- |
| `POST /auth/register` | no | no | no | public |
| `POST /auth/login` | no | no | no | public |
| `GET /auth/me` | yes | no | no | authenticated profile |
| `GET /venues` | no | no | no | public |
| `GET /events` | no | no | no | public |
| `GET /events/{eventId}` | no | no | no | public |
| `GET /events/{eventId}/seats` | no | no | no | public |
| `GET /events/{eventId}/seats/{inventoryId}` | no | no | no | public |
| `POST /admin/events` | admin JWT | no | no | event creation now requires an admin token in the orchestrator |
| `/credits/topup/*` | yes | yes | **yes** | webhook is backend-to-backend only; use idempotency keys |
| `/purchase/*` | yes | yes | **yes** | purchase operations; distributed locks on holds |
| `/tickets/*` | yes | yes | no | these routes are served by `qr-orchestrator` at the gateway |
| `GET /marketplace` | no | no | no | public browse route |
| `POST /marketplace/list` | yes | yes | no | listing creation |
| `DELETE /marketplace/{listingId}` | yes | yes | no | delist |
| `/transfer/*/verify` | yes | yes | no | **rate limited**: max 3 OTP attempts per 15 min |
| `/transfer/*` (other) | yes | yes | no | buyer and seller transfer flows; auto-cancel after 24h |
| `/verify/*` | staff JWT | yes | no | JWT must contain `role=staff`; `venueId` is also used if present |

## Route map used by the frontend

### Public customer pages

- `/`
- `/events`
- `/events/{eventId}`
- `/login`
- `/register`

### Authenticated customer pages

- `/credits/topup`
- `/tickets`
- `/tickets/{ticketId}/qr`
- `/marketplace`
- `/transfer/{transferId}`
- `/profile`

### Staff pages

- QR scan flow posting to `POST /verify/scan`
- manual verification flow posting to `POST /verify/manual`

## Exact frontend endpoints

### Auth

| Method | Path | Request body | Success shape |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | `email`, `password`, `phoneNumber`, optional `role`, optional `venueId` | `{ "data": { "userId", "email", "role", "createdAt" } }` |
| `POST` | `/auth/login` | `email`, `password` | `{ "data": { "token", "expiresAt", "user": { "userId", "email", "role" } } }` |
| `GET` | `/auth/me` | none | `{ "data": { "userId", "email", "phoneNumber", "role", "isFlagged", "createdAt" } }` |

Register example:

```json
{
  "email": "buyer@example.com",
  "password": "Password123!",
  "phoneNumber": "+6591234567"
}
```

Login response example:

```json
{
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expiresAt": "2026-03-29T12:00:00+00:00",
    "user": {
      "userId": "usr_001",
      "email": "buyer@example.com",
      "role": "user"
    }
  }
}
```

### Events and venues

| Method | Path | Query or body | Success shape |
| --- | --- | --- | --- |
| `GET` | `/venues` | none | raw venue-service payload, typically `{ "venues": [...] }` |
| `GET` | `/events` | optional `type`, `page`, `limit` | `{ "data": { "events": [...], "pagination": {...} } }` |
| `GET` | `/events/{eventId}` | none | `{ "data": { ...event, "venue": {...} } }` |
| `GET` | `/events/{eventId}/seats` | none | `{ "data": { "eventId", "seats": [...] } }` |
| `GET` | `/events/{eventId}/seats/{inventoryId}` | none | `{ "data": { ...seat, "event": {...}, "venue": {...} } }` |
| `POST` | `/admin/events` | event creation payload | `{ "data": { "eventId", "seatsCreated" } }` |

Event seat-map response example:

```json
{
  "data": {
    "eventId": "evt_001",
    "seats": [
      {
        "inventoryId": "inv_001",
        "seatId": "seat_001",
        "status": "available",
        "heldUntil": null,
        "rowNumber": "A",
        "seatNumber": "1",
        "price": 88.0
      }
    ]
  }
}
```

Current implementation notes:

- `GET /events` now applies `type`, `page`, and `limit` in `event-service` and returns pagination metadata
- `POST /admin/events` now requires an admin JWT at the orchestrator

### Credits

Frontend base path:

- `https://ticketremasterapi.hong-yi.me/credits`
- `http://localhost:8000/credits`

| Method | Path | Auth | Request body | Success shape |
| --- | --- | --- | --- | --- |
| `GET` | `/credits/balance` | JWT + `apikey` | none | `{ "data": { "userId", "creditBalance", ... } }` |
| `POST` | `/credits/topup/initiate` | JWT + `apikey` | `amount` | `{ "data": { "clientSecret", "paymentIntentId", "amount" } }` |
| `POST` | `/credits/topup/confirm` | JWT + `apikey` | `paymentIntentId` | `{ "data": { "status", "new_balance" } }` or `{ "data": { "status": "already_processed" } }` |
| `GET` | `/credits/transactions` | JWT + `apikey` | optional `page`, `limit` query | `{ "data": { "transactions": [...], "pagination": {...} } }` |

**Important notes on top-up operations:**

- Use **idempotency keys** on both `initiate` and `confirm` to prevent duplicate charges
- If the same `Idempotency-Key` is sent within 24 hours, returns the original response
- Handle `429` rate limiting with exponential backoff
- The `already_processed` status indicates an idempotent retry succeeded

Top-up initiate example:

```json
{
  "amount": 100
}
```

Top-up initiate response:

```json
{
  "data": {
    "clientSecret": "cs_test_...",
    "paymentIntentId": "pi_123",
    "amount": 100
  }
}
```

Top-up confirm example:

```json
{
  "paymentIntentId": "pi_123"
}
```

Webhook note:

- `POST /credits/topup/webhook` exists, but it is intended for Stripe-to-backend delivery, not frontend calls

### Purchase

Frontend base path:

- `https://ticketremasterapi.hong-yi.me/purchase`
- `http://localhost:8000/purchase`

| Method | Path | Auth | Request body | Success shape |
| --- | --- | --- | --- | --- |
| `POST` | `/purchase/hold/{inventoryId}` | JWT + `apikey` | none | `{ "data": { "inventoryId", "status": "held", "heldUntil", "holdToken" } }` |
| `DELETE` | `/purchase/hold/{inventoryId}` | JWT + `apikey` | `holdToken` | `{ "data": { "inventoryId", "status": "available" } }` |
| `POST` | `/purchase/confirm/{inventoryId}` | JWT + `apikey` | `eventId`, `holdToken` | `{ "data": { "ticketId", "eventId", "venueId", "inventoryId", "price", "status", "createdAt" } }` |

**Important notes on purchase operations:**

- Seat holds use **distributed locks** to prevent double-booking
- Hold tokens are valid for **5 minutes** (TTL queue with automatic expiration)
- Use **idempotency keys** on `confirm` to prevent duplicate purchases
- Handle `409 Conflict` when seat is no longer available (lock released)
- Handle `408/504` timeouts with retry using same idempotency key

Hold response example:

```json
{
  "data": {
    "inventoryId": "inv_001",
    "status": "held",
    "heldUntil": "2026-03-29T12:15:00+00:00",
    "holdToken": "c378f45d-4236-4d49-8d93-d5e965964ada"
  }
}
```

Confirm request example:

```json
{
  "eventId": "evt_001",
  "holdToken": "c378f45d-4236-4d49-8d93-d5e965964ada"
}
```

Important route note:

- the frontend should not call `GET /tickets` on `ticket-purchase-orchestrator`
- Kong maps `/tickets/*` to `qr-orchestrator`, so customer ticket listing should use the ticket routes documented in the next section

### Tickets and QR

Frontend base path:

- `https://ticketremasterapi.hong-yi.me/tickets`
- `http://localhost:8000/tickets`

| Method | Path | Auth | Request body | Success shape |
| --- | --- | --- | --- | --- |
| `GET` | `/tickets` | JWT + `apikey` | none | `{ "data": { "tickets": [...] } }` |
| `GET` | `/tickets/{ticketId}/qr` | JWT + `apikey` | none | `{ "data": { "ticketId", "qrHash", "generatedAt", "expiresAt", "event", "venue" } }` |

Ticket list response example:

```json
{
  "data": {
    "tickets": [
      {
        "ticketId": "tkt_001",
        "status": "active",
        "price": 88.0,
        "createdAt": "2026-03-29T12:00:00+00:00",
        "event": {
          "eventId": "evt_001",
          "name": "Taylor Swift | The Eras Tour",
          "date": "2026-06-15T19:30:00+00:00"
        },
        "venue": {
          "venueId": "ven_001",
          "name": "Singapore Indoor Stadium"
        }
      }
    ]
  }
}
```

QR response example:

```json
{
  "data": {
    "ticketId": "tkt_001",
    "qrHash": "a3f9d2e1b8c74f6a91e2d3b4c5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
    "generatedAt": "2026-03-29T12:00:00+00:00",
    "expiresAt": "2026-03-29T12:01:00+00:00",
    "event": {
      "name": "Taylor Swift | The Eras Tour",
      "date": "2026-06-15T19:30:00+00:00"
    },
    "venue": {
      "name": "Singapore Indoor Stadium",
      "address": "2 Stadium Walk"
    }
  }
}
```

### Marketplace

Frontend base path:

- `https://ticketremasterapi.hong-yi.me/marketplace`
- `http://localhost:8000/marketplace`

| Method | Path | Auth | Query or body | Success shape |
| --- | --- | --- | --- | --- |
| `GET` | `/marketplace` | public | optional `eventId`, `page`, `limit` | `{ "data": { "listings": [...], "pagination": {...} } }` |
| `POST` | `/marketplace/list` | JWT + `apikey` | `ticketId`, optional `price` | `{ "data": { "listingId", "ticketId", "sellerId", "price", "status", "createdAt" } }` |
| `DELETE` | `/marketplace/{listingId}` | JWT + `apikey` | none | `{ "data": { "listingId", "status": "cancelled" } }` |

Marketplace browse response example:

```json
{
  "data": {
    "listings": [
      {
        "listingId": "lst_001",
        "ticketId": "tkt_001",
        "sellerId": "usr_002",
        "sellerName": "seller",
        "price": 88.0,
        "status": "active",
        "createdAt": "2026-03-29T12:00:00+00:00",
        "event": {
          "eventId": "evt_001",
          "name": "Taylor Swift | The Eras Tour",
          "date": "2026-06-15T19:30:00+00:00"
        }
      }
    ],
    "pagination": {}
  }
}
```

Current implementation note:

- `page` and `limit` are applied in `marketplace-service`
- `eventId` filtering is applied in `marketplace-orchestrator` after ticket and event enrichment, because the listing record itself does not own `eventId`

### Transfer

Frontend base path:

- `https://ticketremasterapi.hong-yi.me/transfer`
- `http://localhost:8000/transfer`

| Method | Path | Auth | Request body | Success shape |
| --- | --- | --- | --- | --- |
| `POST` | `/transfer/initiate` | JWT + `apikey` | `listingId` | `{ "data": { "transferId", "status", "message" } }` |
| `POST` | `/transfer/{transferId}/seller-accept` | JWT + `apikey` | none | `{ "data": { "transferId", "status", "message" } }` |
| `POST` | `/transfer/{transferId}/buyer-verify` | JWT + `apikey` | `otp` | `{ "data": { "transferId", "status", "message" } }` |
| `POST` | `/transfer/{transferId}/seller-reject` | JWT + `apikey` | none | `{ "data": { "transferId", "status", "message" } }` |
| `POST` | `/transfer/{transferId}/seller-verify` | JWT + `apikey` | `otp` | `{ "data": { "transferId", "status", "completedAt", "ticket" } }` |
| `GET` | `/transfer/pending` | JWT + `apikey` | none | `{ "data": { "transfers": [...] } }` |
| `GET` | `/transfer/{transferId}` | JWT + `apikey` | none | `{ "data": { ...transfer } }` |
| `POST` | `/transfer/{transferId}/resend-otp` | JWT + `apikey` | none | `{ "data": { "message" } }` |
| `POST` | `/transfer/{transferId}/cancel` | JWT + `apikey` | none | `{ "data": { "transferId", "status" } }` |

**Important notes on OTP verification:**

- OTP endpoints (`buyer-verify`, `seller-verify`) enforce **rate limiting**: max 3 attempts per 15 minutes
- Returns `429 Too Many Requests` when limit is exceeded
- Frontend should disable verify button and show countdown timer on `429`
- Transfers auto-cancel after 24 hours if not completed (see `transfer_expired` notifications)

Initiate request example:

```json
{
  "listingId": "lst_001"
}
```

Initiate response example:

```json
{
  "data": {
    "transferId": "txr_001",
    "status": "pending_seller_acceptance",
    "message": "Request sent to seller. Pending acceptance."
  }
}
```

Transfer-state guidance:

- initiate creates a transfer and notifies the seller
- seller accept sends OTP to the buyer
- buyer verify sends OTP to the seller
- seller verify executes the credit and ownership saga
- resend OTP is state-dependent and only works in the relevant pending OTP states

### Verification

Staff app base path:

- `https://ticketremasterapi.hong-yi.me/verify`
- `http://localhost:8000/verify`

| Method | Path | Auth | Request body | Success shape |
| --- | --- | --- | --- | --- |
| `POST` | `/verify/scan` | staff JWT + `apikey` | `qrHash` | `{ "data": { "result": "SUCCESS", "ticketId", "scannedAt", "event", "seat", "owner" } }` |
| `POST` | `/verify/manual` | staff JWT + `apikey` | `ticketId` | `{ "data": { "result": "SUCCESS", "ticketId", "scannedAt", "event", "seat", "owner" } }` |

Scan request example:

```json
{
  "qrHash": "a3f9d2e1b8c74f6a91e2d3b4c5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4"
}
```

## Integration guidance

### Customer top-up flow

1. call `POST /credits/topup/initiate` with an `Idempotency-Key` header
2. confirm Stripe payment in the frontend using the returned `clientSecret`
3. call `POST /credits/topup/confirm` with the `paymentIntentId` and the same `Idempotency-Key`
4. refresh `GET /credits/balance` and `GET /credits/transactions`
5. handle `429` rate limiting with exponential backoff

### Purchase flow

1. call `GET /events/{eventId}/seats`
2. call `POST /purchase/hold/{inventoryId}` - seat is now locked with a distributed lock
3. keep the returned `holdToken` (valid for 5 minutes)
4. call `POST /purchase/confirm/{inventoryId}` with `eventId`, `holdToken`, and an `Idempotency-Key`
5. handle `409 Conflict` if seat was released (hold expired or double-booked)
6. refresh `GET /tickets`
7. if you receive `408` or `504`, retry with the same `Idempotency-Key`

### Marketplace flow

1. call `GET /marketplace` with optional `eventId`, `page`, `limit` filters
2. call `POST /marketplace/list` to list an active ticket
3. use `POST /transfer/initiate` when the buyer starts a purchase from a listing
4. follow the transfer flow with proper OTP rate limiting awareness

### Transfer flow with OTP rate limiting

1. call `POST /transfer/initiate` with `listingId`
2. seller calls `POST /transfer/{transferId}/seller-accept`
3. buyer calls `POST /transfer/{transferId}/buyer-verify` with OTP
   - **Rate limit**: max 3 attempts per 15 minutes
   - If `429` is returned, disable the verify button and show countdown
4. seller calls `POST /transfer/{transferId}/seller-verify` with OTP
   - Same rate limiting applies
5. handle `transfer_expired` notifications for auto-cancelled transfers (24h timeout)

### Best practices for reliability

- **Always use idempotency keys** for state-changing operations (top-up, purchase, transfer)
- **Implement exponential backoff** for retries on `429`, `503`, `408`, `504`
- **Show clear user feedback** when rate limits are hit (countdown timers)
- **Handle graceful shutdown** by retrying `503` responses after a delay
- **Monitor transfer expiration** and update UI when auto-cancel occurs

## Error handling expectations

Common error format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human readable message"
  }
}
```

Some services also enrich errors with:

- `status`
- `traceId`
- `details`

Frontend handling guidance:

- treat `401` as missing or expired JWT
- treat `403` as permission failure such as wrong owner or non-staff verification access
- treat `402` from purchase or transfer flows as insufficient credits
- treat `409` and `410` in purchase flows as seat-state conflicts or expired holds
- treat `429` as Kong rate limiting, not a backend crash
- treat `408` or `504` as timeout from backend services (auto-retry with idempotency key recommended)
- treat `503` as graceful shutdown in progress (wait and retry)

Suggested user copy:

| Scenario | Recommended UI copy |
| --- | --- |
| CORS or gateway connectivity failure | `We couldn't connect to TicketRemaster right now. Please refresh and try again.` |
| Expired auth | `Your session has expired. Please sign in again.` |
| Seat hold expired | `That seat is no longer reserved. Please choose a seat again.` |
| Insufficient credits | `You do not have enough credits for this action. Please top up and try again.` |
| Rate limited | `Too many requests were made in a short time. Please wait a moment and try again.` |
| Temporary backend issue | `TicketRemaster is temporarily unavailable. Please try again shortly.` |
| Request timeout | `This action took too long. Please try again.` |
| Service maintenance | `TicketRemaster is performing maintenance. Please try again in a moment.` |

## Reliability features

The backend now includes several reliability improvements that affect frontend behavior:

### Idempotency keys

For critical operations (purchase, transfer, top-up), include an `Idempotency-Key` header with a unique UUID to prevent duplicate processing:

```javascript
// Example: prevent duplicate purchase confirmations
const idempotencyKey = crypto.randomUUID();
fetch('/purchase/confirm/inv_001', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${jwt}`,
    'apikey': API_KEY,
    'Idempotency-Key': idempotencyKey
  },
  body: JSON.stringify({ eventId: 'evt_001', holdToken: 'abc123' })
});
```

If the same key is sent within 24 hours, the backend returns the original response instead of reprocessing.

### Rate limiting on OTP verification

The OTP verification endpoints (`/transfer/*/buyer-verify`, `/transfer/*/seller-verify`) now enforce rate limiting:
- Maximum 3 attempts per 15 minutes per transfer
- Returns `429 Too Many Requests` when exceeded
- Frontend should disable the verify button and show a countdown timer

### Timeout configuration

All HTTP calls between services now have configurable timeouts:
- Default: 30 seconds for purchase/transfer operations
- Default: 10 seconds for read operations
- Frontend should handle `408 Request Timeout` and `504 Gateway Timeout` gracefully

### Auto-cancel for stuck transfers

Transfers that remain in pending state for more than 24 hours are automatically cancelled:
- Backend publishes a `transfer_expired` notification
- Frontend should listen for this event and update the UI accordingly
- Users receive a notification when their transfer expires

### Graceful shutdown

During deployments or maintenance, services perform graceful shutdown:
- New requests are rejected with `503 Service Unavailable`
- In-flight requests are allowed to complete (up to 30 seconds)
- Frontend should implement exponential backoff retry for `503` responses

### Distributed locks for concurrent operations

Seat hold operations now use distributed locking to prevent double-booking:
- Multiple users attempting to hold the same seat simultaneously are serialized
- First come, first served with proper conflict resolution
- Frontend receives clear `409 Conflict` errors when a seat is no longer available

## Developer shortcuts

### Gateway

- `http://localhost:8000`

### Swagger UIs

- `http://localhost:8100/apidocs` - auth-orchestrator
- `http://localhost:8101/apidocs` - event-orchestrator
- `http://localhost:8102/apidocs` - credit-orchestrator
- `http://localhost:8103/apidocs` - ticket-purchase-orchestrator
- `http://localhost:8104/apidocs` - qr-orchestrator
- `http://localhost:8105/apidocs` - marketplace-orchestrator
- `http://localhost:8106/apidocs` - transfer-orchestrator
- `http://localhost:8107/apidocs` - ticket-verification-orchestrator

### Testing reliability features

```javascript
// Test idempotency
const key = 'test-idempotency-key-123';
fetch('/credits/topup/initiate', {
  method: 'POST',
  headers: { 'Idempotency-Key': key, ... },
  body: JSON.stringify({ amount: 100 })
});
// Same key returns cached response, no duplicate charge

// Test rate limiting
for (let i = 0; i < 5; i++) {
  fetch('/transfer/txr_001/buyer-verify', {
    method: 'POST',
    body: JSON.stringify({ otp: '123456' })
  });
  // After 3 attempts, receives 429
}

// Test graceful shutdown handling
// During deployment, services return 503
// Frontend should retry with exponential backoff
```

### Kubernetes deployment status

The system is deployed on Kubernetes with **2 pods per service** for high availability:

```bash
# Check service health
kubectl get pods -n ticketremaster-core

# All services should show 2/2 Running
# Example output:
# user-service-5b6c4469fb-abc12   1/1     Running   0
# user-service-5b6c4469fb-def34   1/1     Running   0
```

Use [API.md](API.md) for the combined offline reference and `openapi.unified.json` for the unified OpenAPI document.