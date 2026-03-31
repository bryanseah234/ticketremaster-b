# TicketRemaster API Reference

This document provides a complete API reference for the TicketRemaster backend.

## Base URL

- **Local Development**: `http://localhost:8000`
- **Production**: `https://ticketremasterapi.hong-yi.me`

## Authentication

Most endpoints require authentication via JWT token:

```
Authorization: Bearer <jwt_token>
```

Some endpoints also require an API key for rate limiting:

```
apikey: <api_key>
```

## Response Format

### Success Response

```json
{
  "data": { /* response data */ },
  "message": "Optional success message"
}
```

### Error Response

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "status": 400,
    "traceId": "trace_abc123"
  }
}
```

## Endpoints

### Authentication

#### Register User

```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword",
  "phoneNumber": "+1234567890"
}
```

**Response:**
```json
{
  "data": {
    "userId": "user_123",
    "email": "user@example.com",
    "role": "user"
  },
  "access_token": "jwt_token_here",
  "refresh_token": "refresh_token_here"
}
```

#### Login

```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:** Same as register

#### Get Current User

```http
GET /auth/me
Authorization: Bearer <token>
```

**Response:**
```json
{
  "data": {
    "userId": "user_123",
    "email": "user@example.com",
    "phoneNumber": "+1234567890",
    "role": "user",
    "isFlagged": false,
    "createdAt": "2024-01-01T00:00:00Z"
  }
}
```

### Events

#### List Events

```http
GET /events?type=concert&page=1&limit=20
```

**Response:**
```json
{
  "data": {
    "events": [
      {
        "eventId": "evt_123",
        "name": "Taylor Swift - Eras Tour",
        "date": "2025-06-15T19:30:00Z",
        "venueId": "venue_456",
        "price": 149.99,
        "type": "concert",
        "venue": {
          "venueId": "venue_456",
          "name": "Madison Square Garden",
          "address": "4 Pennsylvania Plaza, New York"
        },
        "seatsAvailable": 1250
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 50
    }
  }
}
```

#### Get Event Details

```http
GET /events/{eventId}
```

**Response:**
```json
{
  "data": {
    "eventId": "evt_123",
    "name": "Taylor Swift - Eras Tour",
    "date": "2025-06-15T19:30:00Z",
    "description": "The Eras Tour concert experience",
    "venueId": "venue_456",
    "type": "concert",
    "price": 149.99,
    "image": "/hero-concert.jpeg",
    "venue": {
      "venueId": "venue_456",
      "name": "Madison Square Garden",
      "address": "4 Pennsylvania Plaza, New York"
    },
    "seatsAvailable": 1250
  }
}
```

#### Search Events

```http
GET /events/search?q=taylor&type=concert
```

### Seats

#### Get Seat Map

```http
GET /events/{eventId}/seats
Authorization: Bearer <token>
apikey: <api_key>
```

**Response:**
```json
{
  "data": {
    "seats": [
      {
        "seatId": "seat_123",
        "rowNumber": "A",
        "seatNumber": "1",
        "section": "Floor",
        "inventoryId": "inv_456",
        "status": "available",
        "price": 149.99
      }
    ]
  }
}
```

### Purchases

#### Hold Seat

```http
POST /purchase/hold
Authorization: Bearer <token>
apikey: <api_key>
Idempotency-Key: unique_request_id
Content-Type: application/json

{
  "eventId": "evt_123",
  "seatIds": ["seat_123", "seat_124"]
}
```

**Response:**
```json
{
  "data": {
    "holdId": "hold_789",
    "holdsUntil": "2025-03-30T10:15:00Z",
    "totalAmount": 299.98
  }
}
```

#### Confirm Purchase

```http
POST /purchase/confirm
Authorization: Bearer <token>
apikey: <api_key>
Idempotency-Key: unique_request_id
Content-Type: application/json

{
  "holdId": "hold_789",
  "paymentMethod": "credits"
}
```

**Response:**
```json
{
  "data": {
    "purchaseId": "pur_123",
    "status": "confirmed",
    "tickets": [
      {
        "ticketId": "tkt_123",
        "seatId": "seat_123",
        "qrHash": "qr_hash_abc"
      }
    ]
  }
}
```

### Tickets

#### Get My Tickets

```http
GET /tickets
Authorization: Bearer <token>
apikey: <api_key>
```

**Response:**
```json
{
  "data": {
    "tickets": [
      {
        "ticketId": "tkt_123",
        "eventId": "evt_456",
        "seatId": "seat_789",
        "status": "valid",
        "purchasedAt": "2025-03-30T10:00:00Z",
        "event": {
          "eventId": "evt_456",
          "name": "Taylor Swift - Eras Tour",
          "date": "2025-06-15T19:30:00Z"
        },
        "seat": {
          "seatId": "seat_789",
          "rowNumber": "A",
          "seatNumber": "1",
          "section": "Floor"
        }
      }
    ]
  }
}
```

#### Get Ticket QR Code

```http
GET /tickets/{ticketId}/qr
Authorization: Bearer <token>
```

### Transfers

#### Initiate Transfer

```http
POST /transfer/initiate
Authorization: Bearer <token>
apikey: <api_key>
Idempotency-Key: unique_request_id
Content-Type: application/json

{
  "ticketId": "tkt_123",
  "toUserEmail": "recipient@example.com"
}
```

**Response:**
```json
{
  "data": {
    "transferId": "xfer_123",
    "status": "pending",
    "expiresAt": "2025-04-06T10:00:00Z"
  }
}
```

#### Accept Transfer

```http
POST /transfer/{transferId}/accept
Authorization: Bearer <token>
apikey: <api_key>
Content-Type: application/json

{
  "otpCode": "123456"
}
```

### Marketplace

#### List Marketplace Listings

```http
GET /marketplace?eventId=evt_123&page=1&limit=20
```

**Response:**
```json
{
  "data": {
    "listings": [
      {
        "listingId": "list_123",
        "ticketId": "tkt_456",
        "eventId": "evt_123",
        "price": 199.99,
        "status": "active",
        "createdAt": "2025-03-01T09:00:00Z",
        "event": {
          "eventId": "evt_123",
          "name": "Taylor Swift - Eras Tour",
          "date": "2025-06-15T19:30:00Z"
        }
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 50
    }
  }
}
```

#### Create Listing

```http
POST /marketplace/list
Authorization: Bearer <token>
apikey: <api_key>
Content-Type: application/json

{
  "ticketId": "tkt_123",
  "price": 199.99
}
```

### Credits

#### Get Credit Balance

```http
GET /credits/balance
Authorization: Bearer <token>
apikey: <api_key>
```

**Response:**
```json
{
  "data": {
    "userId": "user_123",
    "balance": 500.00,
    "currency": "USD",
    "updatedAt": "2025-03-30T10:00:00Z"
  }
}
```

#### Top Up Credits

```http
POST /credits/topup/initiate
Authorization: Bearer <token>
apikey: <api_key>
Idempotency-Key: unique_request_id
Content-Type: application/json

{
  "amount": 100.00,
  "paymentMethod": "stripe"
}
```

### Verification

#### Verify Ticket (Staff Only)

```http
GET /verify/{qrHash}
Authorization: Bearer <staff_token>
apikey: <api_key>
```

**Response:**
```json
{
  "data": {
    "isValid": true,
    "ticket": {
      "ticketId": "tkt_123",
      "eventId": "evt_456",
      "seatId": "seat_789",
      "ownerId": "user_123",
      "status": "valid"
    },
    "event": {
      "eventId": "evt_456",
      "name": "Taylor Swift - Eras Tour",
      "date": "2025-06-15T19:30:00Z"
    }
  }
}
```

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid input data |
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource conflict |
| `SEAT_UNAVAILABLE` | 409 | Seat already held or sold |
| `SEAT_ALREADY_SOLD` | 409 | Seat has been sold |
| `HOLD_EXPIRED` | 410 | Seat hold has expired |
| `INSUFFICIENT_CREDITS` | 402 | Not enough credits |
| `OTP_REQUIRED` | 400 | OTP verification required |
| `OTP_INVALID` | 400 | Invalid OTP code |
| `OTP_EXPIRED` | 410 | OTP code expired |
| `TRANSFER_IN_PROGRESS` | 409 | Transfer already pending |
| `TRANSFER_NOT_FOUND` | 404 | Transfer not found |
| `NOT_SEAT_OWNER` | 403 | User doesn't own the ticket |
| `SELF_TRANSFER` | 400 | Cannot transfer to self |
| `EMAIL_ALREADY_EXISTS` | 409 | Email already registered |
| `RATE_LIMITED` | 429 | Too many requests |

## Rate Limiting

API rate limits are enforced per endpoint:

| Endpoint | Limit |
|----------|-------|
| `/auth/register` | 5 requests/minute |
| `/auth/login` | 10 requests/minute |
| All other endpoints | 50 requests/minute |

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Time when limit resets

## Idempotency

State-changing operations (POST, PUT, DELETE) support idempotency keys:

```
Idempotency-Key: unique_request_identifier
```

If the same key is sent within 24 hours, the server returns the cached response instead of repeating the operation.

## WebSocket Notifications

For real-time updates, connect to the WebSocket server:

```javascript
const socket = io('wss://ticketremasterapi.hong-yi.me');

socket.on('connect', () => {
  socket.emit('subscribe', { channel: 'seat_update' });
});

socket.on('seat_update', (data) => {
  console.log('Seat updated:', data);
});
```

See [services/notification-service/NOTIFICATIONS.md](services/notification-service/NOTIFICATIONS.md) for details.

## OpenAPI Documentation

Interactive API documentation is available at:
- Local: `http://localhost:810X/apidocs` (per orchestrator)
- Combined: `openapi.unified.json` in repository root
