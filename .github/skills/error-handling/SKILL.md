---
name: error-handling
description: How to handle and return errors in all TicketRemaster services. Covers the standard error envelope, error codes by category, HTTP status mapping, and exception handling patterns.
---

# Error Handling Patterns

## When to Use

Use this skill whenever returning errors from any endpoint or handling exceptions in orchestrator flows. All services MUST use the same error format.

## Standard Error Response Envelope

```python
# ALWAYS use this format for errors
return jsonify({
    "success": False,
    "error_code": "SEAT_UNAVAILABLE",
    "message": "This seat is currently held by another user."
}), 409
```

## Error Codes by Category

### Seat / Inventory Errors (Orchestrator ↔ Inventory)

| Code | HTTP | Meaning |
|---|---|---|
| `SEAT_UNAVAILABLE` | 409 | Seat is HELD or SOLD |
| `SEAT_NOT_FOUND` | 404 | Seat ID doesn't exist |
| `SEAT_ALREADY_CHECKED_IN` | 409 | Entry log already has SUCCESS |

### User / Auth Errors (Orchestrator ↔ User Service)

| Code | HTTP | Meaning |
|---|---|---|
| `AUTH_INVALID_CREDENTIALS` | 401 | Wrong email/password |
| `AUTH_TOKEN_EXPIRED` | 401 | JWT has expired |
| `AUTH_MISSING_TOKEN` | 401 | No auth header |
| `INSUFFICIENT_CREDITS` | 402 | User balance < ticket price |
| `USER_NOT_FOUND` | 404 | User ID doesn't exist |

### Order Errors (Orchestrator ↔ Order Service)

| Code | HTTP | Meaning |
|---|---|---|
| `ORDER_NOT_FOUND` | 404 | Order ID doesn't exist |
| `PAYMENT_HOLD_EXPIRED` | 410 | 5-min TTL elapsed |
| `DUPLICATE_TRANSFER` | 409 | Active transfer exists for seat |

### Verification Errors (Scenario 3)

| Code | HTTP | Meaning |
|---|---|---|
| `QR_INVALID` | 400 | AES decryption failed |
| `QR_EXPIRED` | 400 | Timestamp > 60 seconds old |
| `WRONG_HALL` | 400 | Presented hall ≠ expected hall |

### System Errors

| Code | HTTP | Meaning |
|---|---|---|
| `SERVICE_UNAVAILABLE` | 503 | Downstream service unreachable |
| `INTERNAL_ERROR` | 500 | Unexpected exception |

## Flask Exception Handler Pattern

Register global error handlers in `create_app()`:

```python
from werkzeug.exceptions import HTTPException

def create_app():
    app = Flask(__name__)

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return jsonify({
                "success": False,
                "error_code": "HTTP_ERROR",
                "message": e.description,
            }), e.code

        # Unexpected error — log and return 500
        app.logger.exception("Unhandled exception")
        return jsonify({
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "message": "An internal error occurred.",
        }), 500

    return app
```

## Orchestrator Exception Handling

In orchestrator flows, catch specific error codes from downstream services:

```python
response = httpx.post(f"{USER_SVC}/credits/deduct", json=payload)

if response.status_code != 200:
    error = response.json()
    if error.get("error_code") == "INSUFFICIENT_CREDITS":
        # Compensate: release seat
        inventory_stub.ReleaseSeat(release_request)
        raise InsufficientCreditsError(error.get("message"))
```

## Must-Do Rules

1. **Never expose stack traces** in production responses
2. **Always include `error_code`** — clients use this for programmatic handling
3. **Always include `message`** — this is shown to end users
4. **Log full exception details** server-side with `logger.exception()`
5. **Return `success: false`** — never omit this field on errors

## References

- `API.md` Section 3 — Full error code reference
- `INSTRUCTIONS.md` Section 10 — Logging & Observability
