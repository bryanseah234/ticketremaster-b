# TicketRemaster API Testing Guide (TEST.md)

This guide provides step-by-step instructions for QA and developers to test the backend API endpoints using Postman or cURL.

**Base URL:**
All requests must go to the API Gateway running on port `8000`.

- Local: `http://localhost:8000/api`
- Cloudflare Tunnel: `https://ticketremasterapi.hong-yi.me/api`
- Production: `https://your-domain.com/api`

---

## Table of Contents

1. [Authenticated Testing (Auth Flow)](#2-authentication-flow-testing)
2. [Event & Admin Testing](#3-event--admin-testing)
3. [Purchasing Flow Testing](#4-purchasing-flow-testing)
4. [Security & Gateway Testing](#5-security--gateway-testing)
5. [Marketplace Flow Testing](#6-marketplace-flow-testing)
6. [Transfer Flow Testing (P2P)](#7-transfer-flow-testing-p2p)
7. [Tickets & QR Testing](#75-tickets--qr-testing)
8. [Credits & Internal Testing](#8-credits--internal-testing)
9. [Proactive Risk Check Testing](#85-proactive-risk-check-testing)
10. [Database CRUD Verification (Manual SQL)](#9-database-crud-verification-manual-sql)
11. [End-to-End Verification Checklist](#10-end-to-end-verification-checklist)
12. [Automated Test Script](#11-automated-test-script)

---

## Seeded Test Accounts

- Non-admin: `user1@example.com` / `password123`
- Admin: `admin@example.com` / `password123`
- OTP mock code (dev): `123456`

---

## 1. Global Pre-requisites

### 1.1 Kong API Key Requirement

All endpoints prefixed with `/api` are protected by Kong.
In **Postman**, go to the "Headers" tab and add:

- Key: `apikey`
- Value: `tk_front_123456789`

### 1.2 Rate Limiting & Bot Detection

- **Rate Limit:** Kong enforces a strict rate limit of `50 requests per minute` per IP address. Exceeding this returns `429 Too Many Requests`.
- **Bot Detection:** Scraper tools like `curl` and `python-requests` without a `User-Agent` spoof will be returned a `403 Forbidden`. Postman is globally allowed.

---

## 2. Authentication Flow Testing

### 2.1 Register a New Account (Step 1)

- **Endpoint:** `POST /api/auth/register`
- **Body:**

  ```json
  {
      "email": "qa_test@example.com",
      "phone": "+6591234567",
      "password": "password123"
  }
  ```

- **Expected Status:** `201 Created`
- **Expected Output:**

  ```json
  {
      "success": true,
      "data": {
          "status": "PENDING_VERIFICATION",
          "message": "OTP sent to phone",
          "user_id": "<uuid-here>"
      }
  }
  ```

- *Make note of the `user_id`.*

### 2.2 Attempting to Login early (Should Fail)

- **Endpoint:** `POST /api/auth/login`
- **Body:**

  ```json
  {
      "email": "qa_test@example.com",
      "password": "password123"
  }
  ```

- **Expected Status:** `403 Forbidden`
- **Expected Output:**

  ```json
  {
      "success": false,
      "error_code": "UNVERIFIED_ACCOUNT",
      "message": "Please verify your phone number before logging in."
  }
  ```

### 2.3 Verify Account via OTP

- **Endpoint:** `POST /api/auth/verify-registration`
- **Body:**

  ```json
  {
      "user_id": "<uuid-from-step-2.1>",
      "otp_code": "123456"
  }
  ```

  *(Note: unless you set up the real SMU SMS API and used a real phone, this will fail in live QA environments unless mocked. To bypass in dev, use the pre-seeded users).*
- **Expected Status:** `200 OK`
- **Expected Output:** Returns the JSON Web Tokens (Access and Refresh).

### 2.4 Login Successfully

Use the pre-seeded test accounts if you cannot verify OTP via phone.

- **Endpoint:** `POST /api/auth/login`
- **Body:**

  ```json
  {
      "email": "user1@example.com",
      "password": "password123"
  }
  ```

- **Expected Status:** `200 OK`
- **Expected Output:**
  Returns `access_token` and `refresh_token`. Capture the `access_token` and add it as a Bearer Token (`Authorization: Bearer <token>`) for all subsequent authenticated requests.

### 2.5 Refresh Token

- **Endpoint:** `POST /api/auth/refresh`
- **Auth:** `Authorization: Bearer <refresh_token>` (use the `refresh_token` from login, NOT the access token)
- **Expected Status:** `200 OK`
- **Expected Output:** Returns a new `access_token`.

### 2.6 Logout

- **Endpoint:** `POST /api/auth/logout`
- **Auth:** Bearer Token (access token)
- **Expected Status:** `200 OK`
- **Expected Output:** Token is blocklisted. Subsequent requests with this token return `401`.

---

## 3. Event & Admin Testing

### 3.1 Fetch Public Events

- **Endpoint:** `GET /api/events`
- **Expected Status:** `200 OK`
- **Expected Output:** Assortment of public Events in a paginated array.

### 3.2 Create Event (Requires Admin)

1. Login with Admin credentials: `admin@example.com` / `password123` to get an Admin JWT.
2. In Postman, switch `Authorization` type to `Bearer Token` and paste the JWT.

- **Endpoint:** `POST /api/admin/events`
- **Body:**

  ```json
  {
      "name": "QA Testing Concert",
      "venue": {
          "name": "QA Stadium",
          "address": "123 Beta Test Road"
      },
      "hall_id": "HALL-QA",
      "event_date": "2026-12-31T20:00:00Z",
      "total_seats": 50,
      "pricing_tiers": {
          "CAT1": 150.00
      }
  }
  ```

- **Expected Status:** `201 Created`
- **Expected Output:**

  ```json
  {
      "success": true,
      "data": {
          "event_id": "<uuid>",
          "seats_created": 50
      }
  }
  ```

### 3.3 Get Admin Dashboard

- **Endpoint:** `GET /api/admin/events/{event_id}/dashboard`
- **Auth:** Bearer Token (Admin JWT)
- **Expected Status:** `200 OK`
- **Expected Output:** Aggregated event data with seat counts by status (available, held, sold).

---

## 4. Purchasing Flow Testing

1. Get an `event_id` from `GET /api/events`.
2. Get a specific `seat_id` array from `GET /api/events/{event_id}`.
3. Keep your `Authorization: Bearer <user1-token>` attached.

### 4.1 Reserve Seat

- **Endpoint:** `POST /api/reserve`
- **Body:**

  ```json
  {
      "seat_id": "<valid-seat-id>"
  }
  ```

- **Expected Status:** `200 OK`
- **Expected Output:** `status: "HELD"` and an `order_id`. You now have exactly 5 minutes to pay.

### 4.2 Pay For Seat (Happy Path)

- **Endpoint:** `POST /api/pay`
- **Body:**

  ```json
  {
      "order_id": "<order-id-from-step-4.1>"
  }
  ```

- **Expected Status:** `200 OK`
- **Expected Output:**

  ```json
  {
      "success": true,
      "data": {
          "status": "CONFIRMED",
          "credits_charged": 150.00,
          "remaining_balance": 850.00
      }
  }
  ```

### 4.3 Reserve Seat (Flagged Account / Proactive Risk Check)

Login as `user2@example.com` (which is seeded with `is_flagged: true`). Attempt to reserve a seat.

- **Endpoint:** `POST /api/reserve`
- **Expected Status:** `428 Precondition Required`
- **Expected Output:**

  ```json
  {
      "success": false,
      "error_code": "OTP_REQUIRED",
      "message": "High risk account. OTP verification required before reservation."
  }
  ```

> **Note:** With the proactive risk check, flagged users now receive `428 OTP_REQUIRED` at **reservation time** (before the seat is locked), not just at payment time.

### 4.4 Reserve by Category

- **Endpoint:** `POST /api/reserve-by-category`
- **Auth:** Bearer Token
- **Body:**

  ```json
  {
      "event_id": "<event_id>",
      "category": "CAT1"
  }
  ```

- **Expected Status:** `200 OK` (randomly assigns an available seat in that category)
- **Expected Output:** Same as 4.1 — returns `order_id`, `seat_id`, `status: "HELD"`.

### 4.5 Verify OTP (Purchase Context)

- **Endpoint:** `POST /api/verify-otp`
- **Auth:** Bearer Token
- **Body:**

  ```json
  {
      "otp_code": "123456",
      "context": "purchase",
      "reference_id": "<order_id>"
  }
  ```

- **Expected Status:** `200 OK` if OTP is valid.

---

## 5. Security & Gateway Testing

1. **Test Global Rate Limiting:** Run a Postman Collection Runner to spam `GET /api/events` 51 times in a loop with no delay.
   - *Expected:* The 51st request should break and return `HTTP 429 Too Many Requests`. This proves Kong Rate Limiting is active.
2. **Test SMS Rate Limiting:** Spam the `POST /api/auth/register` endpoint 6 times in a row.
   - *Expected:* The 6th request should fail with `HTTP 429 Too Many Requests`. This proves the SMS Gateway throttle (5 registrations/minute) is active.
3. **Test Direct Port Bypass:** Attempt to call `POST http://localhost:5000/api/auth/login` (directly calling User service).
   - *Expected:* This should ideally be blocked by a VPC firewall in Production, but locally it proves that hitting `8000` is the actual proper ingress.
4. **Test Missing API Key:** Uncheck the `apikey` header in Postman on any call.
   - *Expected:* `HTTP 401 Unauthorized` returning `No API key found in request`.

---

## 6. Marketplace Flow Testing

### 6.1 List Ticket on Marketplace

- **Endpoint:** `POST /api/marketplace/list`
- **Auth:** Bearer Token (Seller)
- **Body:**

  ```json
  {
      "seat_id": "<your-owned-seat-id>",
      "asking_price": 500.00
  }
  ```

- **Expected Status:** `200 OK`
- **Expected DB State:** `marketplace_listings` table (orders-db) has a new `ACTIVE` row. `seats` table (seats-db) status changes to `LISTED`.

### 6.2 Browse Listings

- **Endpoint:** `GET /api/marketplace/listings?status=ACTIVE`
- **Expected Status:** `200 OK`
- **Expected Output:** Array containing the listing created in 6.1.

### 6.3 Buy from Marketplace

1. Login as a different user (e.g., `user2@example.com`).
2. Ensure user has enough credits (`GET /api/credits/balance`).

- **Endpoint:** `POST /api/marketplace/buy`
- **Auth:** Bearer Token (Buyer)
- **Body:**

  ```json
  {
      "listing_id": "<listing-id-from-6.1>"
  }
  ```

- **Expected Status:** `200 OK`
- **Expected Output:** `status: "PENDING_TRANSFER"`.
- **Expected DB State:** Buyer's credits deducted (escrow_hold). Listing status in `orders-db` changes to `PENDING_TRANSFER`.

### 6.4 Approve Sale (Seller)

1. Login back as the seller.

- **Endpoint:** `POST /api/marketplace/approve`
- **Auth:** Bearer Token (Seller)
- **Body:**

  ```json
  {
      "listing_id": "<listing-id>",
      "otp_code": "123456"
  }
  ```

- **Expected Status:** `200 OK`
- **Expected DB State:** `seats` table `owner_user_id` updated to buyer. Credits released to seller. Listing status `COMPLETED`.

---

## 7. Transfer Flow Testing (P2P)

### 7.1 Initiate Transfer

- **Endpoint:** `POST /api/transfer/initiate`
- **Auth:** Bearer Token
- **Body:**

  ```json
  {
      "seat_id": "<seat-id>",
      "recipient_email": "user2@example.com"
  }
  ```

- **Expected Status:** `200 OK`, returns `transfer_id`.

### 7.2 Confirm Transfer (Dual OTP)

- **Endpoint:** `POST /api/transfer/confirm`
- **Auth:** Bearer Token
- **Body:**

  ```json
  {
      "transfer_id": "<transfer_id>",
      "seller_otp": "123456",
      "buyer_otp": "123456"
  }
  ```

- **Expected Status:** `200 OK`. Seat ownership changes in `seats-db`. Credits transferred.

### 7.3 Dispute Transfer

- **Endpoint:** `POST /api/transfer/dispute`
- **Auth:** Bearer Token (either party)
- **Body:**

  ```json
  {
      "transfer_id": "<transfer_id>",
      "reason": "Suspected unauthorized transfer"
  }
  ```

- **Expected Status:** `200 OK`. Transfer status → `DISPUTED`. Credits frozen.

### 7.4 Reverse Transfer

- **Endpoint:** `POST /api/transfer/reverse`
- **Auth:** Bearer Token (admin or authorized party)
- **Body:**

  ```json
  {
      "transfer_id": "<transfer_id>"
  }
  ```

- **Expected Status:** `200 OK`. Ownership reverted to seller. Credits returned to buyer.

---

## 7.5. Tickets & QR Testing

### 7.5.1 Get My Tickets

- **Endpoint:** `GET /api/tickets`
- **Auth:** Bearer Token
- **Expected Status:** `200 OK`
- **Expected Output:** Array of tickets owned by the authenticated user.

### 7.5.2 Generate QR Code

- **Endpoint:** `GET /api/tickets/{seat_id}/qr`
- **Auth:** Bearer Token (must own the seat)
- **Expected Status:** `200 OK`
- **Expected Output:** Encrypted QR payload (AES-256-GCM). Valid for 60 seconds.

### 7.5.3 Staff QR Verification

- **Endpoint:** `POST /api/verify`
- **Auth:** Bearer Token (staff)
- **Body:**

  ```json
  {
      "qr_payload": "<encrypted_qr_from_7.5.2>",
      "hall_id": "HALL-A"
  }
  ```

- **Expected Status:** `200 OK` with result `SUCCESS` if ticket is valid.
- **Failure Cases:** `EXPIRED` (>60s), `QR_INVALID` (tampered), `DUPLICATE` (already scanned), `WRONG_HALL`, `NOT_FOUND`, `UNPAID`.

---

## 8. Credits & Internal Testing

### 8.1 Check Balance

- **Endpoint:** `GET /api/credits/balance`
- **Expected Status:** `200 OK`.

### 8.2 Top-up Credits (Stripe)

- **Endpoint:** `POST /api/credits/topup`
- **Auth:** Bearer Token
- **Body:** `{ "amount": 100 }`
- **Expected Status:** `200 OK`. Returns a Stripe `client_secret` for frontend payment completion.

### 8.3 Get User Profile

- **Endpoint:** `GET /api/users/{user_id}`
- **Auth:** Bearer Token
- **Expected Status:** `200 OK`
- **Expected Output:** User object including `email`, `credit_balance`, `is_flagged`, `is_admin`.

---

## 8.5. Proactive Risk Check Testing

The Orchestrator now calls `GET /users/{user_id}/risk` **before** locking a seat. This blocks flagged users at reservation time rather than at payment time.

### 8.5.1 Flagged User Reserve → 428

1. Login as `user2@example.com` (is_flagged = true).
2. Attempt to reserve a seat.

- **Endpoint:** `POST /api/reserve`
- **Expected Status:** `428 Precondition Required`
- **Expected Output:** `error_code: "OTP_REQUIRED"` — returned **before** any seat lock is acquired.

### 8.5.2 Normal User Reserve → 200

1. Login as `user1@example.com` (is_flagged = false).
2. Reserve a seat.

- **Endpoint:** `POST /api/reserve`
- **Expected Status:** `200 OK` — risk check passes silently.

---

## 9. Database CRUD Verification (Manual SQL)

Use a tool like `psql` or DBeaver to connect to the local ports.

### 9.1 User Service (`users-db` : 5434)

- **Read User:** `SELECT * FROM users WHERE email = 'qa_test@example.com';`
- **Update Credits:** `UPDATE users SET credit_balance = 1000 WHERE email = 'user1@example.com';` (Useful for testing)
- **Delete User:** `DELETE FROM users WHERE user_id = '...';` (Verify cascading transactions delete if applicable)

### 9.2 Event Service (`events-db` : 5436)

- **Read Event:** `SELECT * FROM events WHERE name = 'QA Testing Concert';`
- **Update Event:** `UPDATE events SET name = 'QA Updated Concert' WHERE event_id = '...';`

### 9.3 Order Service (`orders-db` : 5435)

- **Read Order:** `SELECT * FROM orders WHERE user_id = '...';`
- **Read Marketplace:** `SELECT * FROM marketplace_listings;`
- **Read Transfers:** `SELECT * FROM transfers;`

### 9.4 Inventory Service (`seats-db` : 5433)

- **Read Seat:** `SELECT * FROM seats WHERE seat_id = '...';`
- **Update Seat Status:** `UPDATE seats SET status = 'AVAILABLE' WHERE seat_id = '...';` (Useful for resetting tests)

---

## 10. End-to-End Verification Checklist

- [ ] Register -> Verify OTP -> Login -> Refresh Token -> Logout.
- [ ] Create Event (Admin) -> Get Dashboard -> Check seat counts.
- [ ] Reserve -> Pay (Success) -> Check `orders-db` & `seats-db` status `SOLD`.
- [ ] Reserve by Category -> Verify random seat assigned.
- [ ] Get My Tickets -> Generate QR -> Verify QR (staff scan).
- [ ] List on Marketplace -> Buy -> Approve -> Check ownership transfer.
- [ ] Transfer P2P (Initiate -> Confirm) -> Check ownership change.
- [ ] Transfer Dispute -> Transfer Reverse -> Verify rollback.
- [ ] Flagged user reserve -> Verify `428 OTP_REQUIRED` at reservation time (proactive risk check).
- [ ] Verify OTP -> Retry reserve after OTP clearance.
- [ ] Check credit balance -> Top-up -> Verify balance update.
- [ ] Missing API key -> Verify `401`.
- [ ] Bot User-Agent -> Verify `403`.

---

## 11. Automated Test Script

A comprehensive Python test script is available that tests all endpoints listed above:

```bash
python tests/test_all_endpoints.py
```

**Features:**
- Spoofs browser `User-Agent` to pass Kong bot-detection
- Includes `apikey` header for Kong API key auth
- Tests all 9 sections: Auth, Events, Purchase, Security, Tickets/QR, Marketplace, Transfer, Credits, Risk Check
- Reports PASS/FAIL/SKIP for each test case with a summary
- Uses seeded test data (see `SEED_DATA.md`)
