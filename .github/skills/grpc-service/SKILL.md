---
name: grpc-service
description: How to add or modify gRPC RPCs in the Inventory Service. Covers proto definition, stub generation, service implementation with SQLAlchemy, SELECT FOR UPDATE NOWAIT pattern, and the RabbitMQ DLX consumer.
---

# Adding gRPC RPCs to the Inventory Service

## When to Use

Use this skill when adding new RPCs, modifying existing ones, or working with the Inventory Service's gRPC server, seat locking, or RabbitMQ consumer.

## Architecture Context

The Inventory Service is the ONLY gRPC service. All other services use REST. It owns `seats_db` with the `seats` and `entry_logs` tables.

- **gRPC server** runs on port `50051`
- **HTTP health endpoint** runs on port `8080` (Flask sidecar)
- **RabbitMQ consumer** runs in a separate daemon thread
- All three start from `src/main.py`

## Step-by-Step: Adding a New RPC

### 1. Define in `inventory.proto`

```protobuf
// inventory-service/src/proto/inventory.proto
syntax = "proto3";
package inventory;

service InventoryService {
  rpc NewRpcName (NewRpcRequest) returns (NewRpcResponse);
}

message NewRpcRequest {
  string seat_id = 1;
}

message NewRpcResponse {
  bool success = 1;
}
```

### 2. Generate Python stubs

```bash
python -m grpc_tools.protoc \
  -I src/proto \
  --python_out=src/proto \
  --grpc_python_out=src/proto \
  src/proto/inventory.proto
```

This generates:

- `inventory_pb2.py` — message classes
- `inventory_pb2_grpc.py` — server/client stubs

### 3. Implement the RPC handler

Place logic in the appropriate service file under `src/services/`:

| File | Responsible For |
|---|---|
| `lock_service.py` | `ReserveSeat` (pessimistic locking) |
| `ownership_service.py` | `ConfirmSeat`, `UpdateOwner`, `GetSeatOwner` |
| `verification_service.py` | `VerifyTicket`, `MarkCheckedIn` |

### 4. Pessimistic Locking Pattern

The `ReserveSeat` RPC uses `SELECT FOR UPDATE NOWAIT` to prevent two users from reserving the same seat:

```python
from sqlalchemy import text

def reserve_seat(seat_id, user_id, session):
    try:
        row = session.execute(
            text("""
                SELECT * FROM seats
                WHERE seat_id = :seat_id AND status = 'AVAILABLE'
                FOR UPDATE NOWAIT
            """),
            {"seat_id": seat_id}
        ).fetchone()

        if not row:
            return None  # Seat not available

        session.execute(
            text("""
                UPDATE seats
                SET status = 'HELD',
                    held_by_user_id = :user_id,
                    held_until = NOW() + INTERVAL '5 minutes',
                    updated_at = NOW()
                WHERE seat_id = :seat_id
            """),
            {"seat_id": seat_id, "user_id": user_id}
        )
        session.commit()
        return row

    except Exception:
        session.rollback()
        raise  # NOWAIT raises immediately if row is locked
```

### 5. Seat State Machine

```
AVAILABLE ──reserve──→ HELD ──confirm──→ SOLD ──check-in──→ CHECKED_IN
    ↑                    │
    └───release/DLX──────┘
```

Only valid transitions:

- `AVAILABLE → HELD` (ReserveSeat)
- `HELD → AVAILABLE` (ReleaseSeat / DLX auto-release)
- `HELD → SOLD` (ConfirmSeat)
- `SOLD → CHECKED_IN` (MarkCheckedIn)
- `SOLD → SOLD` with new `owner_user_id` (UpdateOwner — P2P transfer)

### 6. Entry Log Writes

Every QR scan writes to `entry_logs` regardless of outcome:

```python
session.execute(
    text("""
        INSERT INTO entry_logs (log_id, seat_id, scanned_at,
            scanned_by_staff_id, result, hall_id_presented, hall_id_expected)
        VALUES (:log_id, :seat_id, NOW(), :staff_id, :result,
            :hall_presented, :hall_expected)
    """),
    {
        "log_id": str(uuid4()),
        "seat_id": seat_id,
        "staff_id": staff_id,
        "result": result,  # SUCCESS | DUPLICATE | WRONG_HALL | UNPAID | NOT_FOUND | EXPIRED
        "hall_presented": hall_from_qr,
        "hall_expected": hall_from_event,
    }
)
```

## References

- `INSTRUCTIONS.md` Section 3 — `seats_db` schema
- `INSTRUCTIONS.md` Section 8 — RabbitMQ consumer code
- `TASKS.md` Phase 6 — Full implementation checklist
