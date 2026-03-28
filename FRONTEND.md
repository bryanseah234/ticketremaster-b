# TicketRemaster Frontend Integration Contract

## Purpose

This document is the frontend source of truth aligned to:
- `TicketRemaster_API_Reference.pdf`
- `TASK.md`
- Current backend implementation status

It separates:
- Planned frontend-facing orchestrator APIs from API reference
- Currently running backend APIs in this repository (Phase 1-5 atomic + wrappers)

## Current Backend Readiness (TASK Alignment)

### Implemented in repo now
- Phase 0: complete
- Phase 1: complete except 1.4 OutSystems external work
- Phase 2: implemented (including `POST /events` in code)
- Phase 3: complete
- Phase 4: wrappers implemented
- Phase 5: RabbitMQ queue setup + manual runtime queue checks complete

### Not implemented in repo now
- Phase 6 orchestrators
- Phase 7 e2e business journeys
- Phase 8 Kubernetes migration

## Frontend Route Plan

These routes are valid for the frontend application roadmap:

### Public
- `/`
- `/events`
- `/events/:eventId`
- `/login`
- `/register`

### Authenticated
- `/credits/topup`
- `/tickets`
- `/tickets/:ticketId/qr`
- `/marketplace`
- `/transfer/:transferId`
- `/profile`

### Staff App (separate app)
- QR scan page posting to `/verify/scan`

## API Contract for Frontend (From API Reference PDF)

Base rule:
- Frontend must call orchestrators only
- Do not call atomic services directly from browser

## Frontend API Base URL and CORS Rules

### Production
- Frontend origin: `https://ticketremaster.hong-yi.me`
- Public backend API base URL: `https://ticketremasterapi.hong-yi.me`
- Frontend must send browser requests only to the public API hostname and never to internal service names, pod addresses, or direct atomic-service URLs

### Local and Non-Production
- Local frontend origins should be allowed only in non-production environments
- Preview or staging frontend origins should be managed as a separate non-production allowlist, not bundled into production CORS rules
- Frontend developers should expect browser failures if they call the wrong hostname or if their origin is not explicitly approved at the gateway

### Required CORS Expectations
- CORS is enforced centrally at Kong, not by each frontend-facing service independently
- Production origin allowlisting should explicitly include `https://ticketremaster.hong-yi.me`
- Wildcard origin behavior should not be assumed for credentialed browser traffic
- `OPTIONS` preflight requests must succeed for browser integrations to work
- Required request headers should be limited to the approved gateway contract, including `Authorization`, `Content-Type`, and any agreed correlation headers

### Frontend Developer Rules
- Do not hardcode internal Docker or Kubernetes hostnames in frontend code
- Do not call atomic service endpoints directly from the browser even if they appear reachable in local development
- Treat CORS failures as an integration or gateway-policy problem first, not as a reason to bypass Kong
- If preview deployments are used, ensure their browser origin is explicitly added to the non-production allowlist before testing
- Keep all frontend API integrations aligned to the orchestrator route surface documented in this file

### Quick Do / Don't

| Do | Don't |
|---|---|
| Use `https://ticketremasterapi.hong-yi.me` as the browser API base URL in production | Do not call `http://user-service:5000`, `http://kong:8000`, Kubernetes service DNS names, or other private addresses from the browser |
| Send requests only to orchestrator routes documented in this contract | Do not wire the frontend directly to atomic service endpoints |
| Expect CORS to be enforced at Kong | Do not try to bypass CORS by changing frontend code to hit internal hosts |
| Verify preview-origin allowlisting before testing preview deployments | Do not assume every Vercel preview URL is automatically permitted |
| Treat `OPTIONS` failures and `429` responses as gateway integration signals that need handling | Do not interpret them as reasons to remove auth headers, bypass rate limits, or disable browser protections |

### Handling Browser Preflight Failures

- A failed `OPTIONS` preflight usually means the browser origin, method, or request headers are not currently allowed by Kong
- Frontend developers should first verify the request is being sent from an approved origin to `https://ticketremasterapi.hong-yi.me`
- Frontend developers should also verify that only expected headers are being sent, especially `Authorization`, `Content-Type`, and agreed tracing headers
- Do not attempt to fix preflight failures by routing requests directly to internal services or private gateway addresses
- Treat repeated preflight failures as a backend gateway-policy issue that should be coordinated with the platform team

### Handling 429 Responses

- A `429 Too Many Requests` response should be treated as expected protective behavior from Cloudflare or Kong, not as an unexplained backend crash
- Frontend flows should handle `429` gracefully by showing a clear retry message instead of a generic error screen
- User interfaces should avoid bursty retry loops, repeated double-submits, or aggressive polling on protected endpoints such as login, purchase, transfer verification, and staff scan flows
- Where appropriate, frontend retry behavior should use bounded backoff rather than immediate repeated retries
- Frontend developers should capture the request context when reporting 429 issues so the platform team can determine whether the limit was edge-side or gateway-side

### Recommended User-Facing Error Copy

| Scenario | Recommended UI Copy |
|---|---|
| Browser preflight or CORS failure | `We couldn't connect to TicketRemaster right now. Please refresh and try again. If the problem continues, contact support.` |
| Auth or session failure | `Your session has expired or is no longer valid. Please sign in again to continue.` |
| Rate limiting / `429` | `Too many requests were made in a short time. Please wait a moment and try again.` |
| Temporary backend unavailability | `TicketRemaster is temporarily unavailable. Please try again shortly.` |

### Error UX Notes

- Frontend error messaging should stay user-friendly and should not expose internal hostnames, infrastructure details, or implementation-specific gateway terms
- Authentication failures should guide the user toward re-authentication instead of suggesting a generic retry loop
- Rate-limit messaging should encourage waiting before retrying and should avoid implying that payment or purchase state was definitely lost
- Temporary availability messages should avoid promising that a transaction completed unless the frontend has a confirmed success response

### 1) Auth Orchestrator
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

### 2) Credit Orchestrator
- `GET /credits/balance`
- `POST /credits/topup/initiate`
- `POST /credits/topup/webhook`
- `GET /credits/transactions`

### 3) Event Orchestrator
- `GET /events`
- `GET /events/:eventId`
- `GET /events/:eventId/seats`
- `GET /events/:eventId/seats/:inventoryId`

### 4) Ticket Purchase Orchestrator
- `POST /purchase/hold/:inventoryId`
- `POST /purchase/confirm/:inventoryId`

### 5) Marketplace Orchestrator
- `GET /marketplace`
- `POST /marketplace/list`
- `DELETE /marketplace/:listingId`

### 6) Transfer Orchestrator
- `POST /transfer/initiate`
- `POST /transfer/:transferId/buyer-verify`
- `POST /transfer/:transferId/seller-accept`
- `POST /transfer/:transferId/seller-verify`
- `GET /transfer/:transferId`
- `POST /transfer/:transferId/cancel`

### 7) QR Orchestrator
- `GET /tickets`
- `GET /tickets/:ticketId/qr`

### 8) Ticket Verification Orchestrator (staff)
- `POST /verify/scan`

## Atomic Service APIs (Implemented Through Phase 1-5)

These are implemented and running now, but are internal APIs:

### User Service
- `GET /health`
- `GET /users`
- `POST /users`
- `GET /users/:userId`
- `PATCH /users/:userId`
- `GET /users/by-email/:email`

### Venue Service
- `GET /health`
- `GET /venues`
- `GET /venues/:venueId`

### Seat Service
- `GET /health`
- `GET /seats/venue/:venueId`

### Event Service
- `GET /health`
- `GET /events`
- `GET /events/:eventId`
- `POST /events`

### Seat Inventory Service
- `GET /health`
- `GET /inventory/event/:eventId`
- gRPC: `HoldSeat`, `ReleaseSeat`, `SellSeat`, `GetSeatStatus`

### Ticket Service
- `GET /health`
- `POST /tickets`
- `GET /tickets/:ticketId`
- `GET /tickets/owner/:ownerId`
- `GET /tickets/qr/:qrHash`
- `PATCH /tickets/:ticketId`

### Ticket Log Service
- `GET /health`
- `POST /ticket-logs`
- `GET /ticket-logs/ticket/:ticketId`

### Marketplace Service
- `GET /health`
- `POST /listings`
- `GET /listings`
- `GET /listings/:listingId`
- `PATCH /listings/:listingId`

### Transfer Service
- `GET /health`
- `POST /transfers`
- `GET /transfers/:transferId`
- `PATCH /transfers/:transferId`

### Credit Transaction Service
- `GET /health`
- `POST /credit-transactions`
- `GET /credit-transactions/user/:userId`
- `GET /credit-transactions/reference/:referenceId`

### Stripe Wrapper
- `GET /health`
- `POST /stripe/create-payment-intent`
- `POST /stripe/webhook`

### OTP Wrapper
- `GET /health`
- `POST /otp/send`
- `POST /otp/verify`

## RabbitMQ (Phase 5)

Queue topology currently used:
- Exchange: `seat_hold_dlx`
- Queue: `seat_hold_ttl_queue`
- Queue: `seat_hold_expired_queue`
- Queue: `seller_notification_queue`

Manual checks completed:
- TTL expiry routes expired message to DLX queue
- Seller notification queue publish/consume works

## Frontend Implementation Guardrails

- If orchestrators are not deployed, frontend should use mock mode for business flows and keep destructive actions disabled.
- If you need local API integration before Phase 6, build against orchestrator mocks, not atomic services.
- Keep auth/token behavior based on orchestrator JWT model from API reference.
- Use `https://ticketremasterapi.hong-yi.me` as the production API base URL for browser traffic.
- Do not attempt to work around CORS by calling private backend hostnames from the browser.
- Expect Kong to be the enforcement point for CORS, edge policy, and browser-facing routing.

## Explicit Corrections Applied

The previous version of this file contained non-reference endpoints and flow names that do not match the current API reference contract, including:
- `/reserve`
- `/pay`
- `/verify-otp`
- `/auth/verify-registration`
- `/auth/logout`
- `/auth/refresh`
- `/admin/events`
- `/marketplace/buy`
- `/marketplace/approve`

Those are removed from the contract in this document because they are not in the current API reference endpoint list.
