# OutSystems Gatekeeper App — Build Guide

This guide explains how to build the staff QR scanner app in OutSystems, how the verification flow works, and how scanned tickets are marked as used in the backend.

---

## What You Can Import

- Swagger spec: `outsystems/verification-api-swagger.json`
- Reference guide: `outsystems/README.md`

The Swagger spec is importable directly into OutSystems Service Studio and auto-generates the `VerifyTicket` action.

---

## Prerequisites

- OutSystems Service Studio (latest)
- Barcode Plugin from OutSystems Forge
- Staff login flow to obtain a JWT from `POST /api/auth/login`
- Backend base URL:
  - Local: `http://localhost:8000/api`
  - Tunnel/Prod: `https://ticketremasterapi.hong-yi.me/api`

---

## Step-by-Step Build (Service Studio)

### 1) Create or Open the Gatekeeper Module

- Create a new Mobile App or Reactive Web App module named `TicketRemasterGatekeeper`.
- Add a role `Staff` to protect the scan screen.

### 2) Import the Verification API

1. Go to **Logic** → **Integrations** → **REST** → **Consume REST API…**
2. Choose **Import from File**, select `outsystems/verification-api-swagger.json`.
3. Set **Base URL** to your target environment:
   - `http://localhost:8000/api` for local Docker
   - `https://ticketremasterapi.hong-yi.me/api` for tunnel/production
4. Service Studio generates:
   - `VerifyTicket` action
   - Request/response structures

### 3) Add the Authorization Header

In the REST consumer:

- Add header: `Authorization`
- Value: `"Bearer " + StaffSession.AccessToken`

You can set this in the **OnBeforeRequest** callback.

### 4) Build Staff Login (JWT)

Create a login screen that calls `POST /api/auth/login` and stores the access token.

Inputs:

```json
{
  "email": "admin@example.com",
  "password": "password123"
}
```

Store:

- `StaffSession.AccessToken`
- `StaffSession.StaffUserId`
- `StaffSession.CurrentHallId`

### 5) Build the Scan Flow

Client Action flow:

1. `ScanBarcode` (Barcode Plugin)
2. Call `VerifyTicket` with:
   - `qr_payload = ScanResult.Value`
   - `hall_id = StaffSession.CurrentHallId`
   - `staff_id = StaffSession.StaffUserId`
3. Show a result banner based on `data.result`

Suggested UI mapping:

| data.result | UI State | Message |
| --- | --- | --- |
| `SUCCESS` | Green | Show seat row/number + owner name |
| `DUPLICATE` | Yellow | Already checked in |
| `UNPAID` | Red | Incomplete payment |
| `NOT_FOUND` | Red | Possible counterfeit |
| `WRONG_HALL` | Blue | Wrong hall, show expected hall |
| `EXPIRED` | Orange | Expired QR, ask to refresh |

Handle HTTP errors (400/401/503) via exception handler with a retry message.

---

## How Scans Mark Tickets as Used

The OutSystems app does not write to the database directly. It calls the verification endpoint:

```
POST /api/verify
```

When a scan is valid:

- Orchestrator calls Inventory gRPC `MarkCheckedIn(seat_id)`
- Seat status becomes `CHECKED_IN`
- A row is written to `entry_logs` with `result = SUCCESS`

Rejected scans are also logged with result values like `DUPLICATE`, `UNPAID`, `WRONG_HALL`, and `EXPIRED`.

This means the staff app is stateless: it only sends the scan and displays the backend decision.

---

## Inner Workings (Backend Verification)

High-level flow:

1. Decrypt QR payload using `QR_ENCRYPTION_KEY`
2. Validate timestamp (60-second TTL)
3. Verify seat state and ownership
4. Validate event hall
5. Mark checked-in on success
6. Return `data.result` + message

The full backend flow is documented in `instructions.md` under Scenario 3 — Ticket Verification.

---

## Design Alignment with Frontend

To match the customer-facing website:

- Use the same logo and primary color as the frontend UI
- Keep typography simple (single sans-serif family)
- Use large, high-contrast status banners for scan results
- Keep the scan screen minimal: one primary action and one status area

If you want me to align exact colors/typography, I can mirror the frontend styles once you share the design tokens or CSS variables.

---

## Importable Payload Examples

Verify request body:

```json
{
  "qr_payload": "base64-encoded-encrypted-payload",
  "hall_id": "HALL-A",
  "staff_id": "c3d4e5f6-7890-1234-abcd-ef0123456789"
}
```

Success response:

```json
{
  "success": true,
  "data": {
    "result": "SUCCESS",
    "message": "✅ Valid ticket. Welcome!",
    "seat_id": "s1s2s3s4-e5e6-f7f8-g9g0-h1h2h3h4h5h6",
    "row_number": "A",
    "seat_number": 12,
    "owner_name": "John Doe"
  }
}
```

---

## Design Alignment With Frontend

- Dark glassmorphism aesthetic with orange accents
- Use glass surfaces with blur for cards and panels
- Use subtle borders and soft shadow on glass elements
- Typography uses the frontend font stack and high-contrast text
- Accents use orange for primary actions and focus states
- Status banners map to semantic colors: success, warning, disabled
