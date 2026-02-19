# OutSystems Gatekeeper Scanner — Integration Guide

> This folder contains everything the OutSystems team needs to build the **Gatekeeper QR Scanner App** that staff use at venue entry.

---

## What's in This Folder

| File | Purpose |
|---|---|
| `verification-api-swagger.json` | Swagger 2.0 spec for `POST /api/verify`. Import this into Service Studio. |
| `README.md` | This guide. |

---

## Prerequisites

| Dependency | Where to Get It |
|---|---|
| **Barcode Plugin** | OutSystems Forge — install into your environment. Provides `ScanBarcode` client action for camera-based QR scanning. |
| **Staff JWT Token** | Staff members authenticate via the TicketRemaster backend (`POST /api/auth/login`). The token must be sent as `Authorization: Bearer <token>` on every verify call. |

---

## Step-by-Step: Import the API

### 1. Open Service Studio

Open (or create) your Gatekeeper App module.

### 2. Consume REST API

1. Go to **Logic** tab → **Integrations** → right-click **REST** → **Consume REST API…**
2. Choose **Add Single Method** or **Import from Spec** (both work):
   - **Import from Spec (recommended):** Click **Import from File**, select `verification-api-swagger.json`. Service Studio auto-generates the `VerifyTicket` Service Action with correct input/output structures.
   - **Add Single Method:** Manually enter `POST`, paste the endpoint URL (`http://<backend-host>:8000/api/verify`), and define the JSON request/response body using the field specs in `verification-api-swagger.json`.
3. Set the **Base URL** to your environment:
   - Local dev: `http://localhost:8000/api`
   - Production: `https://yourdomain.com/api`

### 3. Wire the Authentication Header

In the generated REST consumer, add a custom header:

| Header Name | Value |
|---|---|
| `Authorization` | `"Bearer " + StaffSession.AccessToken` |

You can set this in the **OnBeforeRequest** callback of the REST consumer.

### 4. Build the Scan Flow

```
┌─────────────────────────────────────────────────┐
│ 1. Staff taps "Scan" button                     │
│                                                 │
│ 2. ScanBarcode action (Barcode Plugin)          │
│    └── returns: ScanResult.Value (string)       │
│                                                 │
│ 3. Call VerifyTicket (generated Service Action)  │
│    ├── qr_payload  = ScanResult.Value            │
│    ├── hall_id     = StaffSession.CurrentHallId  │
│    └── staff_id    = StaffSession.StaffUserId    │
│                                                 │
│ 4. Display result                               │
│    ├── If data.result == "SUCCESS"               │
│    │   └── Show ✅ + seat info (row, seat #)    │
│    └── Else                                     │
│        └── Show ❌ + data.message               │
└─────────────────────────────────────────────────┘
```

### 5. Handle Responses

All scans return HTTP 200 with a `result` field. Map these to your UI:

| `data.result` | Suggested UI |
|---|---|
| `SUCCESS` | ✅ Green banner — show seat row/number and owner name |
| `DUPLICATE` | ⚠️ Yellow banner — "Already Checked In" |
| `UNPAID` | ❌ Red banner — "Incomplete Payment" |
| `NOT_FOUND` | 🚫 Red banner — "Possible Counterfeit" |
| `WRONG_HALL` | 🔄 Blue banner — "Wrong Hall — Go to Hall {X}" (parse from message) |
| `EXPIRED` | ⏰ Orange banner — "Expired QR — Refresh in App" |

HTTP errors (400, 401, 503) should be caught in the flow's exception handler and shown as a generic retry prompt.

---

## Architecture Notes

- The **QR scanning** is handled entirely by the OutSystems Barcode Plugin (camera → string).
- The **verification logic** is entirely server-side — the app just sends the raw scanned string and displays the result.
- QR codes have a **60-second TTL**. If a ticket holder shares a screenshot, it expires before staff can scan it.
- Every scan (pass or fail) is logged server-side for audit. The OutSystems app does not need to persist scan history.

---

## Environment Configuration

Update the Base URL in your REST consumer depending on the deployment environment:

| Environment | Base URL |
|---|---|
| Local Docker dev | `http://localhost:8000/api` |
| Production | `https://yourdomain.com/api` |
