---
name: qr-encryption
description: TicketRemaster QR generation and verification rules with short TTL, ownership checks, and venue validation.
---

# QR Encryption Pattern

## When to Use

Use this skill for `qr-orchestrator` and `ticket-verification-orchestrator` implementation.

## Key Rules

1. Generate QR payloads on demand.
2. Keep payload encrypted and signed by key material in environment.
3. Enforce short TTL before any expensive downstream checks.
4. Validate owner and venue context before allowing check-in.

## QR Payload Format

Logical payload fields before encryption:

```json
{
  "ticketId": "tkt_001",
  "userId": "usr_001",
  "eventId": "evt_001",
  "venueId": "ven_001",
  "generatedAt": "2026-03-22T14:00:00Z"
}
```

## Generation Pattern

```python
def generate_qr_payload(ticket):
    payload = {
        "ticketId": ticket["ticketId"],
        "userId": ticket["ownerId"],
        "eventId": ticket["eventId"],
        "venueId": ticket["venueId"],
        "generatedAt": now_iso(),
    }
    return encrypt_payload(payload)
```

## Verification Pattern

```python
payload = decrypt_payload(qr)
if is_expired(payload["generatedAt"]):
    return {"result": "EXPIRED"}
if payload["venueId"] != presented_venue_id:
    return {"result": "WRONG_HALL"}
```

## Result Codes

| Result | Trigger | Display Message |
|---|---|---|
| `SUCCESS` | All checks pass | Valid ticket |
| `DUPLICATE` | Already checked in | Already checked in |
| `EXPIRED` | Timestamp outside TTL | QR expired |
| `WRONG_HALL` | Venue mismatch | Wrong entrance |
| `NOT_FOUND` | Ticket/owner mismatch | Invalid ticket |

## Must-Do Rules

1. Keep cryptographic key out of logs and responses.
2. Short-circuit on malformed/expired payloads.
3. Validate ownership on every scan request.
4. Keep verification result mapping consistent with frontend expectations.

## References

- [../../../orchestrators/qr-orchestrator/README.md](../../../orchestrators/qr-orchestrator/README.md)
- [../../../orchestrators/ticket-verification-orchestrator/README.md](../../../orchestrators/ticket-verification-orchestrator/README.md)
- [../../../INSTRUCTION.md](../../../INSTRUCTION.md)
- [../orchestrator-flow/SKILL.md](../orchestrator-flow/SKILL.md)
