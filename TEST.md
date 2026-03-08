# TicketRemaster API Testing Guide (TEST.md)

This guide provides step-by-step instructions for QA and developers to test the backend API endpoints using Postman or cURL.

**Base URL:**
All requests must go to the API Gateway running on port `8000`.

- Local: `http://localhost:8000/api`
- Production: `https://your-domain.com/api`

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

### 4.3 Pay For Seat (Flagged Account / OTP required)

Login as `user2@example.com` (which is hardcoded to `is_flagged: true`). Reserve a seat, and trigger logic.

- **Endpoint:** `POST /api/pay`
- **Expected Status:** `428 Precondition Required`
- **Expected Output:**

  ```json
  {
      "success": false,
      "error_code": "OTP_REQUIRED",
      "message": "High risk action. SMS OTP Verification required."
  }
  ```

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
