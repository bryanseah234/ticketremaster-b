---
name: error-handling
description: Error response and propagation patterns for TicketRemaster services and orchestrators.
---

# Error Handling Patterns

## When to Use

Use this skill whenever an endpoint returns non-2xx or when an orchestrator maps downstream failures into frontend-safe responses.

## Response Shape

```python
return jsonify({
    "error": {
        "code": "SEAT_UNAVAILABLE",
        "message": "Seat is already held or sold."
    }
}), 409
```

## Common Error Families

### Inventory/Ticket

| Code | HTTP | Meaning |
|---|---|---|
| `SEAT_UNAVAILABLE` | 409 | Seat is HELD or SOLD |
| `SEAT_NOT_FOUND` | 404 | Seat ID doesn't exist |
| `TICKET_NOT_FOUND` | 404 | Ticket lookup failed |
| `ALREADY_CHECKED_IN` | 409 | Duplicate scan attempt |

### Auth/User

| Code | HTTP | Meaning |
|---|---|---|
| `AUTH_INVALID_CREDENTIALS` | 401 | Wrong email/password |
| `AUTH_TOKEN_EXPIRED` | 401 | JWT has expired |
| `AUTH_MISSING_TOKEN` | 401 | No auth header |
| `AUTH_FORBIDDEN` | 403 | Role not allowed for route |
| `USER_NOT_FOUND` | 404 | User ID doesn't exist |

### Payment/Credit/Transfer

| Code | HTTP | Meaning |
|---|---|---|
| `INSUFFICIENT_CREDITS` | 402 | Balance too low |
| `PAYMENT_HOLD_EXPIRED` | 410 | Hold TTL elapsed |
| `DUPLICATE_TRANSFER` | 409 | Active transfer exists for seat |
| `PAYMENT_ALREADY_PROCESSED` | 409 | Idempotency guard hit |

### QR/Verification

| Code | HTTP | Meaning |
|---|---|---|
| `QR_INVALID` | 400 | Decryption/format failed |
| `QR_EXPIRED` | 400 | TTL exceeded |
| `WRONG_HALL` | 400 | Presented hall ≠ expected hall |

### System Errors

| Code | HTTP | Meaning |
|---|---|---|
| `SERVICE_UNAVAILABLE` | 503 | Downstream service unreachable |
| `INTERNAL_ERROR` | 500 | Unexpected exception |

## Flask Exception Mapping

```python
@app.errorhandler(Exception)
def handle_exception(exc):
    current_app.logger.exception("Unhandled exception")
    return jsonify({
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "Unhandled internal server error."
        }
    }), 500
```

## Orchestrator Propagation Pattern

```python
response = requests.post(url, json=payload, timeout=5)

if response.status_code != 200:
    body = response.json()
    code = body.get("error", {}).get("code", "SERVICE_UNAVAILABLE")
    return jsonify({"error": {"code": code, "message": "Flow failed"}}), response.status_code
```

## Must-Do Rules

1. Never return raw tracebacks to clients.
2. Keep error code naming stable across modules.
3. Log full exception context server-side.
4. Preserve downstream error semantics where useful for client retries.

## References

- [../../../TESTING.md](../../../TESTING.md)
- [../../../INSTRUCTION.md](../../../INSTRUCTION.md)
- [../flask-service/SKILL.md](../flask-service/SKILL.md)
- [../orchestrator-flow/SKILL.md](../orchestrator-flow/SKILL.md)
