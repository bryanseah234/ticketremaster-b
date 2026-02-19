# TicketRemaster — API Endpoint Reference
>
> IS213 Enterprise Solution Development · v1.0

---

## Table of Contents

1. [Overview](#1-overview)
2. [Standard Response Format](#2-standard-response-format)
3. [Standard Error Codes](#3-standard-error-codes)
4. [Authentication Endpoints](#4-authentication-endpoints)
5. [Event Endpoints](#5-event-endpoints)
6. [Purchase Flow Endpoints (Scenario 1)](#6-purchase-flow-endpoints-scenario-1)
7. [Transfer Flow Endpoints (Scenario 2)](#7-transfer-flow-endpoints-scenario-2)
8. [Verification Endpoint (Scenario 3)](#8-verification-endpoint-scenario-3)
9. [Credit & Payment Endpoints](#9-credit--payment-endpoints)
10. [Ticket Endpoints](#10-ticket-endpoints)
11. [Health Check Endpoints](#11-health-check-endpoints)
12. [Internal Service APIs](#12-internal-service-apis)
13. [Swagger / Flasgger Integration Plan](#13-swagger--flasgger-integration-plan)

---

## 1. Overview

### Base URL

All public API requests go through **Kong API Gateway**:

| Environment | Base URL |
|---|---|
| Local dev | `http://localhost:8000/api` |
| Production | `https://yourdomain.com/api` |

### Authentication

All endpoints require a valid JWT in the `Authorization` header unless marked **🔓 Public**.

```
Authorization: Bearer <access_token>
```

### Content Type

All request and response bodies use `application/json`.

---

## 2. Standard Response Format

### Success Response

```json
{
  "success": true,
  "data": { ... }
}
```

### Error Response

```json
{
  "success": false,
  "error_code": "SEAT_UNAVAILABLE",
  "message": "This seat is currently held by another user. Please select a different seat."
}
```

### Paginated Response (where applicable)

```json
{
  "success": true,
  "data": [ ... ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

---

## 3. Standard Error Codes

### Global Errors (any endpoint)

| Error Code | HTTP Status | Description |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing or invalid JWT token |
| `TOKEN_EXPIRED` | 401 | JWT access token has expired — refresh required |
| `FORBIDDEN` | 403 | Valid token but insufficient role/permissions |
| `VALIDATION_ERROR` | 400 | Request body failed schema validation |
| `INVALID_UUID` | 400 | A UUID parameter is malformed |
| `INTERNAL_ERROR` | 500 | Unexpected server error — logged with correlation ID |
| `SERVICE_UNAVAILABLE` | 503 | A downstream service is unreachable |

### Business-Specific Errors

| Error Code | HTTP Status | Used In | Description |
|---|---|---|---|
| `SEAT_NOT_FOUND` | 404 | Reserve, Verify | Seat ID does not exist |
| `SEAT_UNAVAILABLE` | 409 | Reserve | Seat is held or sold by another user |
| `SEAT_ALREADY_SOLD` | 409 | Reserve | Seat has already been purchased |
| `SEAT_NOT_HELD` | 409 | Pay | Seat is not in HELD state (hold may have expired) |
| `HOLD_EXPIRED` | 410 | Pay | 5-minute hold TTL has passed — seat released |
| `INSUFFICIENT_CREDITS` | 402 | Pay, Transfer | User does not have enough credits |
| `ORDER_NOT_FOUND` | 404 | Pay | Order ID does not exist |
| `ORDER_ALREADY_CONFIRMED` | 409 | Pay | Order has already been confirmed |
| `OTP_REQUIRED` | 428 | Pay | High-risk user — OTP verification required before payment |
| `OTP_INVALID` | 401 | Verify OTP, Transfer Confirm | OTP code is incorrect |
| `OTP_EXPIRED` | 410 | Verify OTP, Transfer Confirm | OTP code has expired |
| `OTP_MAX_RETRIES` | 429 | Verify OTP, Transfer Confirm | Maximum OTP attempts exceeded |
| `TRANSFER_NOT_FOUND` | 404 | Transfer Confirm/Dispute/Reverse | Transfer ID does not exist |
| `TRANSFER_INVALID_STATE` | 409 | Transfer Confirm/Dispute/Reverse | Transfer is not in the expected state |
| `TRANSFER_IN_PROGRESS` | 409 | Transfer Initiate | A pending transfer already exists for this seat |
| `NOT_SEAT_OWNER` | 403 | Transfer Initiate, QR Refresh | User does not own this seat |
| `SELF_TRANSFER` | 400 | Transfer Initiate | Cannot transfer a ticket to yourself |
| `USER_NOT_FOUND` | 404 | Multiple | User ID does not exist |
| `EVENT_NOT_FOUND` | 404 | Events | Event ID does not exist |
| `EVENT_ENDED` | 410 | Reserve | Event has already passed |
| `QR_EXPIRED` | 410 | Verify | QR timestamp older than 60 seconds |
| `QR_INVALID` | 400 | Verify | QR payload failed decryption or integrity check |
| `DUPLICATE_ENTRY` | 409 | Verify | Ticket has already been scanned (duplicate entry) |
| `WRONG_HALL` | 400 | Verify | QR hall_id does not match event hall_id |
| `UNPAID_SEAT` | 402 | Verify | Seat is in HELD state — payment not completed |
| `EMAIL_ALREADY_EXISTS` | 409 | Register | Email is already registered |

---

## 4. Authentication Endpoints

### 🔓 `POST /api/auth/register`

Create a new user account.

**Request Body:**

```json
{
  "email": "user@example.com",
  "phone": "+6591234567",
  "password": "securePassword123"
}
```

**Success Response (201):**

```json
{
  "success": true,
  "data": {
    "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "email": "user@example.com",
    "message": "Account created successfully"
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP |
|---|---|---|
| Email already registered | `EMAIL_ALREADY_EXISTS` | 409 |
| Missing required fields | `VALIDATION_ERROR` | 400 |
| Invalid email format | `VALIDATION_ERROR` | 400 |
| Invalid phone format | `VALIDATION_ERROR` | 400 |
| Password too short (< 8 chars) | `VALIDATION_ERROR` | 400 |

---

### 🔓 `POST /api/auth/login`

Authenticate and receive JWT tokens.

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "expires_in": 900,
    "user": {
      "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "email": "user@example.com",
      "credit_balance": 500.00
    }
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP |
|---|---|---|
| Invalid credentials | `UNAUTHORIZED` | 401 |
| Missing email or password | `VALIDATION_ERROR` | 400 |

---

### `POST /api/auth/refresh`

Refresh an expired access token.

**Request Header:**

```
Authorization: Bearer <refresh_token>
```

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 900
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP |
|---|---|---|
| Invalid refresh token | `UNAUTHORIZED` | 401 |
| Refresh token expired | `TOKEN_EXPIRED` | 401 |
| Refresh token blocklisted (logged out) | `UNAUTHORIZED` | 401 |

---

### `POST /api/auth/logout`

Invalidate current tokens (adds to blocklist).

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "message": "Successfully logged out"
  }
}
```

---

## 5. Event Endpoints

### 🔓 `GET /api/events`

List all upcoming events.

**Query Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `page` | int | No | Page number (default: 1) |
| `per_page` | int | No | Items per page (default: 20, max: 100) |

**Success Response (200):**

```json
{
  "success": true,
  "data": [
    {
      "event_id": "a1b2c3d4-...",
      "name": "Taylor Swift Eras Tour SG",
      "venue": {
        "venue_id": "v1v2v3v4-...",
        "name": "Singapore Indoor Stadium"
      },
      "hall_id": "HALL-A",
      "event_date": "2026-06-15T19:00:00Z",
      "total_seats": 5000,
      "available_seats": 3200,
      "pricing_tiers": {
        "CAT1": 350.00,
        "CAT2": 200.00,
        "CAT3": 120.00
      }
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 5,
    "total_pages": 1
  }
}
```

---

### 🔓 `GET /api/events/{event_id}`

Get a single event with seat map / availability.

> **Cross-service assembly (choreography):** The `seats` array in the response is assembled by the **Event Service itself** — it calls the **Inventory Service's internal HTTP endpoint** to fetch seat statuses for the given `event_id`, then merges the result with its own event/venue data before returning the combined response. The Orchestrator is **not** involved in this call. This is an instance of direct service-to-service choreography.

**Path Parameters:**

| Param | Type | Description |
|---|---|---|
| `event_id` | UUID | Event identifier |

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "event_id": "a1b2c3d4-...",
    "name": "Taylor Swift Eras Tour SG",
    "venue": {
      "venue_id": "v1v2v3v4-...",
      "name": "Singapore Indoor Stadium",
      "address": "2 Stadium Walk, Singapore 397691"
    },
    "hall_id": "HALL-A",
    "event_date": "2026-06-15T19:00:00Z",
    "total_seats": 5000,
    "available_seats": 3200,
    "pricing_tiers": {
      "CAT1": 350.00,
      "CAT2": 200.00,
      "CAT3": 120.00
    },
    "seats": [
      {
        "seat_id": "s1s2s3s4-...",
        "row_number": "A",
        "seat_number": 12,
        "status": "AVAILABLE",
        "category": "CAT1",
        "price": 350.00
      }
    ]
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP |
|---|---|---|
| Event not found | `EVENT_NOT_FOUND` | 404 |
| Invalid UUID | `INVALID_UUID` | 400 |

---

## 6. Purchase Flow Endpoints (Scenario 1)

### `POST /api/reserve`

Reserve a seat — places a 5-minute pessimistic lock.

**Request Body:**

```json
{
  "seat_id": "s1s2s3s4-...",
  "user_id": "f47ac10b-..."
}
```

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "order_id": "o1o2o3o4-...",
    "seat_id": "s1s2s3s4-...",
    "status": "HELD",
    "held_until": "2026-02-19T18:15:00Z",
    "ttl_seconds": 300,
    "message": "Seat reserved. Complete payment within 5 minutes."
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP | Detail |
|---|---|---|---|
| Seat held by another user | `SEAT_UNAVAILABLE` | 409 | `SELECT FOR UPDATE NOWAIT` failed — another transaction holds the lock |
| Seat already sold | `SEAT_ALREADY_SOLD` | 409 | Seat status is `SOLD` or `CHECKED_IN` |
| Seat not found | `SEAT_NOT_FOUND` | 404 | seat_id does not exist in seats_db |
| Event already passed | `EVENT_ENDED` | 410 | Event date is in the past |
| User not found | `USER_NOT_FOUND` | 404 | user_id does not exist |

---

### `POST /api/pay`

Confirm payment — deducts credits, finalises purchase.

**Request Body:**

```json
{
  "order_id": "o1o2o3o4-..."
}
```

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "order_id": "o1o2o3o4-...",
    "seat_id": "s1s2s3s4-...",
    "status": "CONFIRMED",
    "credits_charged": 350.00,
    "remaining_balance": 150.00,
    "message": "Purchase confirmed! Your ticket is ready."
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP | Detail |
|---|---|---|---|
| Hold TTL expired | `HOLD_EXPIRED` | 410 | Seat was auto-released by DLX. User must re-reserve. |
| Insufficient credits | `INSUFFICIENT_CREDITS` | 402 | `credit_balance < price`. Redirect to Stripe top-up. |
| High-risk user needs OTP | `OTP_REQUIRED` | 428 | `user.is_flagged = true`. Client must call `/api/verify-otp` first. |
| Order not found | `ORDER_NOT_FOUND` | 404 | order_id does not exist |
| Order already confirmed | `ORDER_ALREADY_CONFIRMED` | 409 | Payment already processed |
| Seat not in HELD state | `SEAT_NOT_HELD` | 409 | Seat status changed unexpectedly |

---

### `POST /api/verify-otp`

Verify OTP for high-risk users during purchase or transfer. Called after receiving `OTP_REQUIRED`.

**Request Body:**

```json
{
  "user_id": "f47ac10b-...",
  "otp_code": "123456",
  "context": "purchase",
  "reference_id": "o1o2o3o4-..."
}
```

`context` = `"purchase"` | `"transfer"` — determines which flow to resume after verification.
`reference_id` = `order_id` (purchase) or `transfer_id` (transfer).

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "verified": true,
    "message": "OTP verified. You may proceed."
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP | Detail |
|---|---|---|---|
| Incorrect OTP | `OTP_INVALID` | 401 | Code does not match |
| OTP expired (>5 min) | `OTP_EXPIRED` | 410 | Request a new OTP |
| Max retries exceeded (3) | `OTP_MAX_RETRIES` | 429 | Flow cancelled. Must re-initiate. |

---

## 7. Transfer Flow Endpoints (Scenario 2)

> Either the **seller** (current ticket owner) or the **buyer** can initiate a transfer.

### `POST /api/transfer/initiate`

Start a P2P ticket transfer. Triggers OTP for both parties.

**Request Body:**

```json
{
  "seat_id": "s1s2s3s4-...",
  "seller_user_id": "f47ac10b-...",
  "buyer_user_id": "b1b2b3b4-...",
  "credits_amount": 300.00
}
```

**Success Response (201):**

```json
{
  "success": true,
  "data": {
    "transfer_id": "t1t2t3t4-...",
    "seat_id": "s1s2s3s4-...",
    "status": "PENDING_OTP",
    "message": "Transfer initiated. Both parties will receive an OTP for verification."
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP | Detail |
|---|---|---|---|
| Seller does not own seat | `NOT_SEAT_OWNER` | 403 | `seat.owner_user_id != seller_user_id` |
| Buyer insufficient credits | `INSUFFICIENT_CREDITS` | 402 | `buyer.credit_balance < credits_amount` |
| Transfer already pending for this seat | `TRANSFER_IN_PROGRESS` | 409 | An `INITIATED` or `PENDING_OTP` transfer exists for this seat_id |
| Self-transfer | `SELF_TRANSFER` | 400 | `seller_user_id == buyer_user_id` |
| Seat not in SOLD state | `SEAT_UNAVAILABLE` | 409 | Can only transfer tickets with status `SOLD` |
| Seller not found | `USER_NOT_FOUND` | 404 | seller_user_id does not exist |
| Buyer not found | `USER_NOT_FOUND` | 404 | buyer_user_id does not exist |
| Seat not found | `SEAT_NOT_FOUND` | 404 | seat_id does not exist |

---

### `POST /api/transfer/confirm`

Confirm transfer with both OTPs. Executes atomic swap (credits + ownership).

**Request Body:**

```json
{
  "transfer_id": "t1t2t3t4-...",
  "seller_otp": "123456",
  "buyer_otp": "654321"
}
```

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "transfer_id": "t1t2t3t4-...",
    "status": "COMPLETED",
    "seat_id": "s1s2s3s4-...",
    "new_owner_user_id": "b1b2b3b4-...",
    "credits_transferred": 300.00,
    "message": "Transfer complete. Ticket ownership updated."
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP | Detail |
|---|---|---|---|
| Seller OTP incorrect | `OTP_INVALID` | 401 | Seller OTP does not match |
| Buyer OTP incorrect | `OTP_INVALID` | 401 | Buyer OTP does not match |
| Either OTP expired | `OTP_EXPIRED` | 410 | Re-initiate transfer |
| Max OTP retries exceeded (3) | `OTP_MAX_RETRIES` | 429 | Transfer auto-cancelled → `FAILED` |
| Transfer not in PENDING_OTP state | `TRANSFER_INVALID_STATE` | 409 | Transfer already completed/cancelled |
| Transfer not found | `TRANSFER_NOT_FOUND` | 404 | transfer_id does not exist |

---

### `POST /api/transfer/dispute`

Flag a transfer for fraud/dispute. Credits are frozen.

**Request Body:**

```json
{
  "transfer_id": "t1t2t3t4-...",
  "reason": "I did not authorise this transfer"
}
```

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "transfer_id": "t1t2t3t4-...",
    "status": "DISPUTED",
    "message": "Dispute recorded. Credits frozen pending investigation."
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP | Detail |
|---|---|---|---|
| Transfer not found | `TRANSFER_NOT_FOUND` | 404 | transfer_id does not exist |
| Transfer not in COMPLETED state | `TRANSFER_INVALID_STATE` | 409 | Can only dispute completed transfers |
| User not party to transfer | `FORBIDDEN` | 403 | Only seller or buyer can dispute |

---

### `POST /api/transfer/reverse`

Reverse a disputed transfer — return ownership to seller, credits to buyer.

**Request Body:**

```json
{
  "transfer_id": "t1t2t3t4-..."
}
```

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "transfer_id": "t1t2t3t4-...",
    "status": "REVERSED",
    "seat_id": "s1s2s3s4-...",
    "restored_owner_user_id": "f47ac10b-...",
    "credits_returned": 300.00,
    "message": "Transfer reversed. Ownership and credits restored."
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP | Detail |
|---|---|---|---|
| Transfer not found | `TRANSFER_NOT_FOUND` | 404 | transfer_id does not exist |
| Transfer not in DISPUTED state | `TRANSFER_INVALID_STATE` | 409 | Can only reverse disputed transfers |
| Buyer no longer has seat (already transferred again) | `SEAT_UNAVAILABLE` | 409 | Seat has changed ownership since dispute |

---

## 8. Verification Endpoint (Scenario 3)

### `POST /api/verify`

Staff scans QR code to verify ticket at venue entry.

**Request Body:**

```json
{
  "qr_payload": "base64-encoded-encrypted-payload",
  "hall_id": "HALL-A",
  "staff_id": "staff-uuid-..."
}
```

**Success Response (200) — Valid Entry:**

```json
{
  "success": true,
  "data": {
    "result": "SUCCESS",
    "seat_id": "s1s2s3s4-...",
    "row_number": "A",
    "seat_number": 12,
    "owner_name": "John Doe",
    "message": "✅ Valid ticket. Welcome!"
  }
}
```

**Rejection Responses (200 with result):**

All rejection cases return HTTP 200 (the API call succeeded) but with a non-SUCCESS `result`. Every scan — pass or fail — is logged to `entry_logs`.

```json
{
  "success": true,
  "data": {
    "result": "DUPLICATE",
    "message": "⚠️ Already Checked In. This ticket was scanned at 18:42:03."
  }
}
```

| Result | Trigger | Display Message |
|---|---|---|
| `SUCCESS` | `seat.status == SOLD`, no prior check-in | ✅ Valid ticket. Welcome! |
| `DUPLICATE` | `entry_logs` has `SUCCESS` record for this seat | ⚠️ Already Checked In |
| `UNPAID` | `seat.status == HELD` | ❌ Incomplete Payment |
| `NOT_FOUND` | seat_id does not exist | 🚫 Possible Counterfeit |
| `WRONG_HALL` | QR `hall_id` ≠ `event.hall_id` | 🔄 Wrong Hall — Go to Hall {X} |
| `EXPIRED` | QR timestamp older than 60 seconds | ⏰ Expired QR — Refresh ticket in app |

**Error Responses (actual failures):**

| Scenario | Error Code | HTTP | Detail |
|---|---|---|---|
| QR decryption failed | `QR_INVALID` | 400 | Payload tampered or wrong encryption key |
| Downstream service unavailable | `SERVICE_UNAVAILABLE` | 503 | Retry scan |

---

## 9. Credit & Payment Endpoints

### `GET /api/credits/balance`

Get the current credit balance for the authenticated user.

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "user_id": "f47ac10b-...",
    "credit_balance": 500.00
  }
}
```

---

### `POST /api/credits/topup`

Create a Stripe Payment Intent for credit top-up.

**Request Body:**

```json
{
  "amount": 100.00
}
```

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "client_secret": "pi_1234_secret_5678",
    "amount": 100.00,
    "currency": "sgd",
    "message": "Complete payment on the frontend using Stripe.js"
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP | Detail |
|---|---|---|---|
| Invalid amount (≤ 0) | `VALIDATION_ERROR` | 400 | Amount must be positive |
| Stripe API error | `INTERNAL_ERROR` | 500 | Payment intent creation failed |

---

### 🔓 `POST /api/webhooks/stripe`

Stripe webhook — called by Stripe on `payment.succeeded`. Adds credits to user balance.

> **Note:** This endpoint is public (no JWT) but validated using the Stripe webhook signature (`STRIPE_WEBHOOK_SECRET`).

**Request Body:** Standard Stripe webhook event payload.

**Success Response (200):**

```json
{
  "received": true
}
```

**Error Responses:**

| Scenario | HTTP | Detail |
|---|---|---|
| Invalid webhook signature | 400 | Signature verification failed |
| Unknown event type | 200 | Acknowledged but ignored |

---

## 10. Ticket Endpoints

### `GET /api/tickets`

List all tickets owned by the authenticated user.

**Success Response (200):**

```json
{
  "success": true,
  "data": [
    {
      "seat_id": "s1s2s3s4-...",
      "event": {
        "event_id": "a1b2c3d4-...",
        "name": "Taylor Swift Eras Tour SG",
        "event_date": "2026-06-15T19:00:00Z",
        "hall_id": "HALL-A"
      },
      "row_number": "A",
      "seat_number": 12,
      "status": "SOLD",
      "price_paid": 350.00,
      "purchased_at": "2026-02-19T10:30:00Z"
    }
  ]
}
```

---

### `GET /api/tickets/{seat_id}/qr`

Generate a fresh QR code payload with a new 60-second timestamp for ticket display.

> Only the current seat owner can request a QR. The client should poll this every ~50 seconds to keep the QR code fresh.

**Path Parameters:**

| Param | Type | Description |
|---|---|---|
| `seat_id` | UUID | Seat identifier |

**Success Response (200):**

```json
{
  "success": true,
  "data": {
    "qr_payload": "base64-encoded-encrypted-payload",
    "generated_at": "2026-02-19T18:10:00Z",
    "expires_at": "2026-02-19T18:11:00Z",
    "ttl_seconds": 60
  }
}
```

**Error Responses:**

| Scenario | Error Code | HTTP | Detail |
|---|---|---|---|
| Not the seat owner | `NOT_SEAT_OWNER` | 403 | JWT user_id ≠ seat.owner_user_id |
| Seat not found | `SEAT_NOT_FOUND` | 404 | seat_id does not exist |
| Seat not in SOLD state | `SEAT_UNAVAILABLE` | 409 | Can only generate QR for owned, sold tickets |

---

## 11. Health Check Endpoints

Each microservice exposes a `GET /health` endpoint. These are used by Docker `healthcheck` directives and can be called for operational monitoring.

### `GET /health`

**Success Response (200):**

```json
{
  "status": "healthy",
  "service": "inventory-service",
  "timestamp": "2026-02-19T18:10:00Z",
  "checks": {
    "database": "connected",
    "rabbitmq": "connected"
  }
}
```

**Unhealthy Response (503):**

```json
{
  "status": "unhealthy",
  "service": "inventory-service",
  "timestamp": "2026-02-19T18:10:00Z",
  "checks": {
    "database": "disconnected",
    "rabbitmq": "connected"
  }
}
```

| Service | Health Check Port | Dependencies Checked |
|---|---|---|
| Inventory Service | 50051 (gRPC) / 8080 (HTTP) | seats_db, RabbitMQ |
| User Service | 5000 | users_db |
| Order Service | 5001 | orders_db |
| Event Service | 5002 | events_db |
| Orchestrator | 5003 | All downstream services |

---

## 12. Internal Service APIs

> These endpoints are **not** exposed through Kong. They are called internally by the Orchestrator.

### 12.1 Inventory Service (gRPC)

Defined in `inventory-service/src/proto/inventory.proto`.

| RPC | Request | Response | Description |
|---|---|---|---|
| `ReserveSeat` | `{seat_id, user_id}` | `{success, held_until}` | `SELECT FOR UPDATE NOWAIT`. Status → `HELD`. |
| `ConfirmSeat` | `{seat_id, user_id}` | `{success, qr_code_hash}` | Status → `SOLD`. Sets `owner_user_id`. |
| `ReleaseSeat` | `{seat_id}` | `{success}` | Status → `AVAILABLE`. Clears hold fields. |
| `UpdateOwner` | `{seat_id, new_owner_id}` | `{success}` | Transfers ownership for P2P transfer. |
| `VerifyTicket` | `{seat_id}` | `{status, owner_user_id, event_id}` | Read-only check for verification flow. |
| `MarkCheckedIn` | `{seat_id}` | `{success}` | Status → `CHECKED_IN`. Writes `entry_log`. |
| `GetSeatOwner` | `{seat_id}` | `{owner_user_id, status}` | Ownership check for transfer validation. |

### 12.2 User Service (REST — Internal)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/users/{user_id}` | Get user profile |
| `GET` | `/users/{user_id}/risk` | Returns `{is_flagged: bool}` |
| `POST` | `/credits/deduct` | Deduct credits: `{user_id, amount}` |
| `POST` | `/credits/transfer` | Atomic swap: `{from_user_id, to_user_id, amount}` |
| `POST` | `/otp/send` | Send OTP via SMU API: `{user_id}` |
| `POST` | `/otp/verify` | Verify OTP: `{user_id, otp_code}` |

### 12.3 Order Service (REST — Internal)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/orders` | Create order: `{user_id, seat_id, event_id, credits_charged}` |
| `PATCH` | `/orders/{order_id}` | Update status: `{status}` |
| `GET` | `/orders?seat_id=` | Get order by seat (verification flow) |
| `POST` | `/transfers` | Create transfer record |
| `PATCH` | `/transfers/{transfer_id}` | Update transfer status |
| `POST` | `/transfers/{transfer_id}/dispute` | Set `DISPUTED` + reason |
| `POST` | `/transfers/{transfer_id}/reverse` | Set `REVERSED` + undo |

### 12.4 Event Service (REST — Internal)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/events` | List all events |
| `GET` | `/events/{event_id}` | Get event details including `hall_id` |

---

## 13. Swagger / Flasgger Integration Plan

### Library

[**Flasgger**](https://github.com/flasgger/flasgger) — a Flask extension that extracts OpenAPI/Swagger specs from Flask view docstrings and serves Swagger UI.

### Setup

```bash
pip install flasgger
```

Add to each Flask service's `requirements.txt`:

```
flasgger==0.9.7.1
```

### Integration (per service)

```python
from flask import Flask
from flasgger import Swagger

app = Flask(__name__)

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}

swagger_template = {
    "info": {
        "title": "TicketRemaster - Orchestrator Service",
        "description": "API documentation for the Orchestrator Service",
        "version": "1.0.0"
    },
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Authorization header. Example: 'Bearer {token}'"
        }
    }
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)
```

### Endpoint Documentation Example

```python
@app.route('/api/reserve', methods=['POST'])
def reserve_seat():
    """
    Reserve a seat for checkout
    ---
    tags:
      - Purchase Flow
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - seat_id
            - user_id
          properties:
            seat_id:
              type: string
              format: uuid
              example: "s1s2s3s4-e5e6-f7f8-g9g0-h1h2h3h4h5h6"
            user_id:
              type: string
              format: uuid
              example: "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    responses:
      200:
        description: Seat reserved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            data:
              type: object
              properties:
                order_id:
                  type: string
                held_until:
                  type: string
                  format: date-time
                ttl_seconds:
                  type: integer
                  example: 300
      409:
        description: Seat unavailable
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            error_code:
              type: string
              example: "SEAT_UNAVAILABLE"
            message:
              type: string
    """
    # ... implementation
```

### Swagger UI Access

| Service | Swagger UI URL |
|---|---|
| Orchestrator | `http://localhost:5003/apidocs/` |
| User Service | `http://localhost:5000/apidocs/` |
| Order Service | `http://localhost:5001/apidocs/` |
| Event Service | `http://localhost:5002/apidocs/` |

### Implementation Tasks

- [ ] Add `flasgger` to each service's `requirements.txt`
- [ ] Add Swagger init boilerplate to each `app.py`
- [ ] Write YAML docstrings for every endpoint (can be done incrementally as services are built)
- [ ] Test Swagger UI loads and all endpoints appear
- [ ] Add `securityDefinitions` for JWT Bearer token
