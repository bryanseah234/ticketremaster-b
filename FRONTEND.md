# TicketRemaster Frontend Integration Contract

This is the current frontend-facing contract for the backend routes exposed through Kong.

## Frontend rules

- call Kong only
- prefer the no-prefix routes such as `/events` and `/auth/login`
- send `Authorization: Bearer <jwt>` on JWT-protected routes
- send `apikey: tk_front_123456789` on Kong-protected route groups
- do not call internal service ports, Docker hostnames, or Kubernetes service DNS names from the browser

## Base URLs

- Local: `http://localhost:8000`
- Shared public backend: `https://ticketremasterapi.hong-yi.me`

Kong also supports `/api/...` aliases, but the frontend should not depend on them for new code.

## Auth and key matrix

| Route group | JWT | apikey | Notes |
| --- | --- | --- | --- |
| `/auth/*` | route-dependent | no | register, verify-registration, and login are public |
| `/venues`, `/events*` | no | no | public browse surface |
| `/admin/events*` | admin JWT | no | admin-only orchestrator guard |
| `/credits*` | yes | yes | customer credit flows |
| `/purchase*` | yes | yes | hold and confirm |
| `/tickets*` | yes | yes | list tickets and generate QR |
| `GET /marketplace` | no | no | public |
| `POST /marketplace/list` | yes | yes | list for resale |
| `DELETE /marketplace/{listingId}` | yes | yes | delist |
| `/transfer*` | yes | yes | buyer and seller flow |
| `/verify*` | staff JWT | yes | staff verification only |

## Current route surface

### Auth

- `POST /auth/register`
- `POST /auth/verify-registration`
- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/logout`
- `POST /auth/logout-all`

Frontend note:

- registration does not immediately return a JWT
- login or successful OTP verification is what returns the token used for subsequent calls

### Events and venues

- `GET /venues`
- `GET /events`
- `GET /events/{eventId}`
- `GET /events/{eventId}/seats`
- `GET /events/{eventId}/seats/{inventoryId}`
- `POST /admin/events`
- `GET /admin/events/{eventId}/dashboard`

### Credits

- `GET /credits/balance`
- `POST /credits/topup/initiate`
- `POST /credits/topup/confirm`
- `GET /credits/transactions`

### Purchase

- `POST /purchase/hold/{inventoryId}`
- `DELETE /purchase/hold/{inventoryId}`
- `POST /purchase/confirm/{inventoryId}`

### Tickets

- `GET /tickets`
- `GET /tickets/{ticketId}/qr`

### Marketplace

- `GET /marketplace`
- `POST /marketplace/list`
- `DELETE /marketplace/{listingId}`

### Transfer

- `POST /transfer/initiate`
- `GET /transfer/pending`
- `GET /transfer/{transferId}`
- `POST /transfer/{transferId}/seller-accept`
- `POST /transfer/{transferId}/seller-reject`
- `POST /transfer/{transferId}/buyer-verify`
- `POST /transfer/{transferId}/seller-verify`
- `POST /transfer/{transferId}/resend-otp`
- `POST /transfer/{transferId}/cancel`

### Staff verification

- `POST /verify/scan`
- `POST /verify/manual`

## Request and response notes

### Register

```json
{
  "email": "buyer@example.com",
  "password": "Password123!",
  "phoneNumber": "+6591234567"
}
```

Returns:

```json
{
  "data": {
    "userId": "usr_001",
    "email": "buyer@example.com",
    "role": "user",
    "createdAt": "2026-04-07T12:00:00+00:00"
  }
}
```

### Login

Returns:

```json
{
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expiresAt": "2026-04-08T12:00:00+00:00",
    "user": {
      "userId": "usr_001",
      "email": "buyer@example.com",
      "role": "user"
    }
  }
}
```

### Purchase hold

The path includes the `inventoryId`. There is no seat-array purchase endpoint in the current orchestrator.

Hold response:

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

Confirm request:

```json
{
  "eventId": "evt_001",
  "holdToken": "c378f45d-4236-4d49-8d93-d5e965964ada"
}
```

### Transfer initiate

The request starts from a marketplace listing:

```json
{
  "listingId": "lst_001"
}
```

### Staff verification

QR verification is now:

```json
{
  "qrHash": "a3f9d2e1..."
}
```

Manual verification is:

```json
{
  "ticketId": "tkt_001"
}
```

## Flow guidance

### Customer purchase flow

1. browse `GET /events`
2. fetch `GET /events/{eventId}/seats`
3. call `POST /purchase/hold/{inventoryId}`
4. keep the returned `holdToken`
5. call `POST /purchase/confirm/{inventoryId}` with `eventId` and `holdToken`
6. refresh `GET /tickets`

### Credit top-up flow

1. call `POST /credits/topup/initiate`
2. confirm the Stripe client secret in the frontend
3. call `POST /credits/topup/confirm`
4. refresh balance and transaction history

### Marketplace transfer flow

1. list a ticket with `POST /marketplace/list`
2. buyer starts with `POST /transfer/initiate`
3. seller accepts
4. buyer verifies OTP
5. seller verifies OTP

## Error handling expectations

- `401` usually means missing or expired JWT, or missing Kong key-auth credential
- `402` means insufficient credits
- `403` means correct authentication but insufficient role or ownership
- `409` means conflicting seat or ticket state
- `410` means purchase hold expired
- `503` usually means a downstream dependency such as OutSystems is unavailable

## Related docs

- [API.md](API.md)
- [TESTING.md](TESTING.md)
- [README.md](README.md)
