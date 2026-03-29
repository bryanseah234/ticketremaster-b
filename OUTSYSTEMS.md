# OutSystems Integration Guide (Credit Service)

## Architecture Overview

The Credit Service uses **OutSystems** as the external system of record for user credit balances. This is a **standard microservice with OutSystems backend** architecture:

- **Backend (this repo):** Provides REST API wrapper endpoints that proxy to OutSystems
- **OutSystems:** External system that owns the authoritative credit balance data
- **Communication:** Backend calls OutSystems via REST with API key authentication

### Integration Pattern

```
Frontend → API Gateway → Credit Orchestrator → credit-transaction-service → OutSystems Credit API
```

The `credit-transaction-service` in this repository acts as a **REST wrapper** around the OutSystems Credit API. It provides:

1. **Transaction logging** (PostgreSQL) - Local record of all credit changes
2. **API abstraction** - Consistent interface regardless of OutSystems implementation
3. **Error handling** - Normalized error responses for frontend consumption

### Data Flow

1. **Credit Balance Read:** `credit-transaction-service` → OutSystems `GET /credits/<user_id>`
2. **Credit Balance Update:** `credit-transaction-service` → OutSystems `PATCH /credits/<user_id>`
3. **Transaction Recording:** Local PostgreSQL (for audit trail)

### PostgreSQL Persistence

The `credit-transaction-service` maintains a local `credit_transactions` table for:
- Audit trail of all credit movements
- Idempotency checking via `referenceId`
- Historical transaction queries

**Note:** The authoritative credit *balance* lives in OutSystems. The local table only stores *transactions*.

---

## Scope

This guide covers how to connect the TicketRemaster backend to the external OutSystems Credit Service for Phase 1.4 and future orchestrators.

Backend components that call OutSystems:
- Auth Orchestrator: initialise user credit record on registration
- Credit Orchestrator: balance read, top-up write
- Ticket Purchase Orchestrator: pre-purchase balance check and deduction
- Transfer Orchestrator: buyer/seller balance movement during P2P transfer

## Required Endpoints in OutSystems

Implement these REST endpoints in OutSystems:

1) `POST /credits`
- Purpose: create initial credit account for a new user
- Request JSON:
```json
{
  "userId": "usr_123",
  "creditBalance": 0
}
```
- Success response: `201`
```json
{
  "success": true,
  "data": {
    "userId": "usr_123",
    "creditBalance": 0
  }
}
```

2) `GET /credits/<user_id>`
- Purpose: retrieve current balance
- Success response: `200`
```json
{
  "success": true,
  "data": {
    "userId": "usr_123",
    "creditBalance": 120.5
  }
}
```

3) `PATCH /credits/<user_id>`
- Purpose: set absolute balance value
- Request JSON:
```json
{
  "creditBalance": 95.5
}
```
- Success response: `200`
```json
{
  "success": true,
  "data": {
    "userId": "usr_123",
    "creditBalance": 95.5
  }
}
```

`PATCH` must return updated `creditBalance` in the same response body.

## Error Envelope Contract

Use this structure for all non-2xx responses:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```

Recommended mapping:
- `400`: `VALIDATION_ERROR`
- `401`: `UNAUTHORIZED`
- `403`: `FORBIDDEN`
- `404`: `USER_NOT_FOUND`
- `409`: `DUPLICATE_RECORD`
- `500`: `INTERNAL_ERROR`

## Authentication Between Backend and OutSystems

Use API key auth from backend to OutSystems:
- Header name: `X-API-KEY`
- Header value: value from `OUTSYSTEMS_API_KEY`

OutSystems should reject missing or invalid keys with `401`/`403`.

## Backend Environment Variables

The backend uses:
- `CREDIT_SERVICE_URL`
- `OUTSYSTEMS_API_KEY`

In Docker, orchestrators should call OutSystems with:
- URL base from `CREDIT_SERVICE_URL`
- `X-API-KEY` header from `OUTSYSTEMS_API_KEY`

## Idempotency and Safety Rules

Apply these rules in orchestrators:
- Registration flow: if OutSystems credit init fails, compensate user creation.
- Stripe webhook flow: check existing `referenceId` in Credit Transaction Service before balance write.
- Ticket purchase and transfer: always re-read latest balance before deduction.
- Transfer saga: compensate in reverse order on downstream failure.

## OutSystems Data Model

Create an entity for credits:
- `UserId` (Text, unique, indexed)
- `CreditBalance` (Decimal)
- `CreatedAt` (DateTime)
- `UpdatedAt` (DateTime)

Constraints:
- Unique index on `UserId`
- `CreditBalance >= 0`

## Validation Rules

Server-side checks:
- `userId` required for POST
- `creditBalance` required and numeric for POST/PATCH
- `creditBalance >= 0`
- Reject malformed JSON

## Connectivity Verification Steps

1) Confirm OutSystems API endpoint base URL.
2) Set backend `.env`:
- `CREDIT_SERVICE_URL=<outsystems-base-url>`
- `OUTSYSTEMS_API_KEY=<shared-secret>`
3) Execute smoke tests:
- `POST /credits` for a new user
- `GET /credits/<user_id>`
- `PATCH /credits/<user_id>`
- `GET /credits/<user_id>` to confirm updated value
4) Verify wrong API key returns `401`/`403`.
5) Verify unknown user returns `404`.

## Postman Smoke Test Examples

Headers:
- `Content-Type: application/json`
- `X-API-KEY: {{outsystems_api_key}}`

Create:
```http
POST {{credit_service_url}}/credits
```
```json
{
  "userId": "usr_demo_001",
  "creditBalance": 0
}
```

Read:
```http
GET {{credit_service_url}}/credits/usr_demo_001
```

Update:
```http
PATCH {{credit_service_url}}/credits/usr_demo_001
```
```json
{
  "creditBalance": 250
}
```
