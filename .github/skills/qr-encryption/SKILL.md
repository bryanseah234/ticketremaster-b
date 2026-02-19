---
name: qr-encryption
description: How to generate and verify QR codes using AES-256-GCM encryption with 60-second TTL. Covers the encryption/decryption pattern, payload format, and anti-fraud validation rules.
---

# QR Code Encryption & Verification

## When to Use

Use this skill when implementing QR code generation (Scenario 1 purchase flow, Scenario 2 transfer) or QR verification (Scenario 3 venue entry).

## Key Rules

1. **QR codes are generated on-demand** — never stored as images
2. **AES-256-GCM encryption** — provides confidentiality + integrity
3. **60-second TTL** — QR must be refreshed before scanning
4. **`QR_ENCRYPTION_KEY` must be exactly 32 bytes** — from `.env`

## QR Payload Format

Plaintext JSON before encryption:

```json
{
  "seat_id": "s1s2s3s4-e5e6-f7f8-g9g0-h1h2h3h4h5h6",
  "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "hall_id": "HALL-A",
  "generated_at": "2026-02-19T18:10:45Z"
}
```

## Encryption (QR Generation)

Called by the Orchestrator at the end of purchase or transfer flows:

```python
import json
import os
import base64
from datetime import datetime, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def generate_qr_payload(seat_id: str, user_id: str, hall_id: str) -> str:
    """Generate an encrypted, base64-encoded QR payload."""

    key = os.environ["QR_ENCRYPTION_KEY"].encode("utf-8")  # Must be 32 bytes
    assert len(key) == 32, "QR_ENCRYPTION_KEY must be exactly 32 bytes"

    payload = json.dumps({
        "seat_id": seat_id,
        "user_id": user_id,
        "hall_id": hall_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }).encode("utf-8")

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM

    ciphertext = aesgcm.encrypt(nonce, payload, None)

    # Prepend nonce to ciphertext, then base64 encode
    return base64.b64encode(nonce + ciphertext).decode("utf-8")
```

## Decryption (QR Verification)

Called by the Orchestrator's verification flow when staff scans a QR code:

```python
def decrypt_qr_payload(encrypted_b64: str) -> dict:
    """
    Decrypt and validate a QR payload.
    Returns the decrypted dict or raises an error.
    """

    key = os.environ["QR_ENCRYPTION_KEY"].encode("utf-8")

    try:
        raw = base64.b64decode(encrypted_b64)
        nonce = raw[:12]
        ciphertext = raw[12:]

        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return json.loads(plaintext.decode("utf-8"))

    except Exception:
        raise QRInvalidError("Failed to decrypt QR payload")
```

## Anti-Fraud Validation (after decryption)

The Orchestrator runs these checks after successful decryption:

```python
from datetime import datetime, timezone, timedelta

def validate_qr(payload: dict, presented_hall_id: str) -> str:
    """
    Validate decrypted QR payload. Returns result code.
    """

    # 1. Check TTL — QR must be < 60 seconds old
    generated_at = datetime.fromisoformat(payload["generated_at"])
    age = datetime.now(timezone.utc) - generated_at
    if age > timedelta(seconds=60):
        return "EXPIRED"

    # 2. Check seat status via Inventory gRPC
    seat = inventory_stub.VerifyTicket(
        VerifyTicketRequest(seat_id=payload["seat_id"])
    )

    if seat.status == "AVAILABLE":
        return "NOT_FOUND"  # Seat was never sold

    if seat.status != "SOLD":
        return "DUPLICATE"  # Already checked in

    # 3. Check owner matches QR
    if seat.owner_user_id != payload["user_id"]:
        return "NOT_FOUND"  # Ownership transferred, old QR is invalid

    # 4. Check hall matches
    event = get_event(seat.event_id)
    if event["hall_id"] != presented_hall_id:
        return "WRONG_HALL"

    # 5. Check for duplicate entry
    has_prior_entry = check_entry_log(payload["seat_id"])
    if has_prior_entry:
        return "DUPLICATE"

    return "SUCCESS"
```

## Result Codes

| Result | Trigger | Display Message |
|---|---|---|
| `SUCCESS` | All checks pass, no prior check-in | ✅ Valid ticket. Welcome! |
| `DUPLICATE` | Entry log already has SUCCESS record | ⚠️ Already Checked In |
| `EXPIRED` | QR timestamp > 60 seconds old | ⏰ Expired QR — Refresh ticket in app |
| `WRONG_HALL` | QR hall ≠ venue hall | 🚫 Wrong Entrance |
| `NOT_FOUND` | Seat unpaid / user mismatch | ❌ Invalid Ticket |

## Must-Do Rules

1. **Never store QR images** — generate on every GET request
2. **Always validate TTL first** — short-circuit before DB calls
3. **Always check `user_id`** — prevents use of transferred tickets' old QRs
4. **Write to `entry_logs` for EVERY scan** — including failures (audit trail)
5. **Return result + display message** — front-end shows the message directly

## References

- `API.md` Section 7.1 — QR Code Specification
- `API.md` Section 8 — Verification Endpoint
- `INSTRUCTIONS.md` Section 7 — Scenario 3 full flow
