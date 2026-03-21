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
