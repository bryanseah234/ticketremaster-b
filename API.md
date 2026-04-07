# TicketRemaster Gateway API Reference

This document is the offline gateway reference for the routes currently exposed through Kong.

## Base URLs

- Local: `http://localhost:8000`
- Shared public URL: `https://ticketremasterapi.hong-yi.me`

Kong also accepts `/api/...` aliases, but new clients should use the no-prefix form.

## Auth model

Headers used across the platform:

```http
Authorization: Bearer <jwt>
apikey: tk_front_123456789
```

Rules:

- public routes need neither header
- JWT-protected routes need `Authorization`
- Kong-protected route groups need both `Authorization` and `apikey`
- staff verification routes require a JWT with `role=staff`
- admin event creation and dashboard routes require an admin JWT

## Response envelope

Success responses normally use:

```json
{
  "data": {}
}
```

Errors use:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```

## Auth routes

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | public | Creates the user, initializes external credit best-effort, sends registration OTP |
| `POST` | `/auth/verify-registration` | public | Verifies OTP and returns JWT |
| `POST` | `/auth/login` | public | Returns JWT |
| `GET` | `/auth/me` | JWT | Current user profile |
| `POST` | `/auth/logout` | JWT | Revokes current token |
| `POST` | `/auth/logout-all` | JWT | Placeholder all-device logout that currently revokes the current token |

Important behavior:

- `POST /auth/register` does not return a JWT
- login or successful registration verification is what produces a token

Example register request:

```json
{
  "email": "buyer@example.com",
  "password": "Password123!",
  "phoneNumber": "+6591234567"
}
```

Example login response:

```json
{
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expiresAt": "2026-04-07T12:00:00+00:00",
    "user": {
      "userId": "usr_001",
      "email": "buyer@example.com",
      "role": "user"
    }
  }
}
```

## Event and venue routes

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| `GET` | `/venues` | public | Returns venue-service payload |
| `GET` | `/events` | public | Supports `type`, `page`, `limit` |
| `GET` | `/events/{eventId}` | public | Event enriched with venue |
| `GET` | `/events/{eventId}/seats` | public | Seat map with inventory state and seat metadata |
| `GET` | `/events/{eventId}/seats/{inventoryId}` | public | Single seat detail |
| `POST` | `/admin/events` | admin JWT | Creates event and seat inventory |
| `GET` | `/admin/events/{eventId}/dashboard` | admin JWT | Revenue and attendee summary |

## Credit routes

| Method | Path | Auth |
| --- | --- | --- |
| `GET` | `/credits/balance` | JWT + apikey |
| `POST` | `/credits/topup/initiate` | JWT + apikey |
| `POST` | `/credits/topup/confirm` | JWT + apikey |
| `POST` | `/credits/topup/webhook` | backend-to-backend |
| `GET` | `/credits/transactions` | JWT + apikey |

Current top-up flow:

1. frontend calls `/credits/topup/initiate`
2. Stripe wrapper creates a PaymentIntent and returns `clientSecret`
3. frontend completes Stripe confirmation
4. frontend calls `/credits/topup/confirm` with `paymentIntentId`
5. credit-orchestrator updates OutSystems and logs the internal ledger record

Example initiate response:

```json
{
  "data": {
    "clientSecret": "cs_test_...",
    "paymentIntentId": "pi_123",
    "amount": 100
  }
}
```

## Purchase routes

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| `POST` | `/purchase/hold/{inventoryId}` | JWT + apikey | Places a 5-minute hold via gRPC |
| `DELETE` | `/purchase/hold/{inventoryId}` | JWT + apikey | Releases a hold early |
| `POST` | `/purchase/confirm/{inventoryId}` | JWT + apikey | Confirms purchase using `eventId` and `holdToken` |

Design notes:

- hold, release, and sell are executed through `seat-inventory-service` gRPC
- a Redis hold cache speeds up confirm-path validation
- RabbitMQ carries hold-expiry messages
- OutSystems credit balance is checked before seat sale is finalized

Example hold response:

```json
{
  "data": {
    "inventoryId": "inv_001",
    "status": "held",
    "heldUntil": "2026-04-07T12:15:00+00:00",
    "holdToken": "c378f45d-4236-4d49-8d93-d5e965964ada"
  }
}
```

Example confirm request:

```json
{
  "eventId": "evt_001",
  "holdToken": "c378f45d-4236-4d49-8d93-d5e965964ada"
}
```

## Ticket and QR routes

| Method | Path | Auth |
| --- | --- | --- |
| `GET` | `/tickets` | JWT + apikey |
| `GET` | `/tickets/{ticketId}/qr` | JWT + apikey |

QR behavior:

- each QR fetch generates a fresh SHA-256 hash
- the hash is persisted on the ticket record
- TTL is currently 60 seconds
- scan-time expiry is enforced by `ticket-verification-orchestrator`

## Marketplace routes

| Method | Path | Auth |
| --- | --- | --- |
| `GET` | `/marketplace` | public |
| `POST` | `/marketplace/list` | JWT + apikey |
| `DELETE` | `/marketplace/{listingId}` | JWT + apikey |

`GET /marketplace` supports `eventId`, `page`, and `limit`.

Implementation note:

- `marketplace-service` stores the listing record
- `marketplace-orchestrator` enriches listings with seller and event data
- the `eventId` filter is applied after enrichment because the raw listing record does not own `eventId`

## Transfer routes

| Method | Path | Auth |
| --- | --- | --- |
| `POST` | `/transfer/initiate` | JWT + apikey |
| `GET` | `/transfer/pending` | JWT + apikey |
| `GET` | `/transfer/{transferId}` | JWT + apikey |
| `POST` | `/transfer/{transferId}/seller-accept` | JWT + apikey |
| `POST` | `/transfer/{transferId}/seller-reject` | JWT + apikey |
| `POST` | `/transfer/{transferId}/buyer-verify` | JWT + apikey |
| `POST` | `/transfer/{transferId}/seller-verify` | JWT + apikey |
| `POST` | `/transfer/{transferId}/resend-otp` | JWT + apikey |
| `POST` | `/transfer/{transferId}/cancel` | JWT + apikey |

Transfer design logic:

- initiation starts from a `listingId`, not a `ticketId`
- seller acceptance sends buyer OTP
- buyer verification sends seller OTP
- seller verification executes the credit and ownership saga
- RabbitMQ is used both for seller notification and timeout scheduling

Example initiate request:

```json
{
  "listingId": "lst_001"
}
```

## Staff verification routes

| Method | Path | Auth |
| --- | --- | --- |
| `POST` | `/verify/scan` | staff JWT + apikey |
| `POST` | `/verify/manual` | staff JWT + apikey |

Scan ordering is intentional:

1. lookup ticket by QR hash
2. validate QR TTL
3. validate event
4. validate sold inventory state
5. validate active ticket state
6. detect duplicate scan from ticket logs
7. validate venue match from staff JWT
8. mark ticket used and append a check-in log

## External ingress route

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/webhooks/stripe` | Routed through Kong to the user-service Stripe webhook ingress |

## Common status codes

| Status | Meaning in this codebase |
| --- | --- |
| `400` | Validation or state mismatch |
| `401` | Missing or invalid JWT, or missing Kong key-auth credential |
| `402` | Insufficient credits |
| `403` | Authenticated but forbidden, such as wrong owner or wrong role |
| `404` | Resource missing |
| `409` | Conflict, duplicate action, concurrent action, or already-used ticket |
| `410` | Expired seat hold |
| `429` | Rate limit |
| `503` | Downstream dependency unavailable |

## Related docs

- [FRONTEND.md](FRONTEND.md)
- [TESTING.md](TESTING.md)
- [OUTSYSTEMS.md](OUTSYSTEMS.md)
