---
name: orchestrator-flow
description: How to implement multi-service orchestration flows (Saga pattern). Covers the coordination pattern between services, compensation/rollback on failure, and the three main scenarios (purchase, transfer, verification).
---

# Implementing Orchestrator Flows (Saga Pattern)

## When to Use

Use this skill when implementing or modifying a multi-step flow in `orchestrator-service/src/orchestrators/`. The Orchestrator is the Saga Manager — it coordinates calls to atomic services and handles compensation (rollback) on failure.

## Architecture Rules

1. **All external traffic** enters through Kong → Orchestrator. No direct client-to-atomic-service calls (except Event Service's choreography for seat availability).
2. **Each step must be compensatable.** If step N fails, undo steps N-1, N-2, ... in reverse order.
3. **gRPC for Inventory** (performance-critical). **REST for User, Order, Event** (standard).
4. **AMQP for async recovery** (RabbitMQ DLX for seat auto-release).
5. **Correlation IDs** must propagate across all calls for tracing.

## Flow Template

```python
# orchestrator-service/src/orchestrators/<flow>_orchestrator.py

def execute_flow(data: dict) -> dict:
    """
    Template for an orchestrator flow with compensation.
    Each step is wrapped in try/except with rollback of prior steps.
    """
    completed_steps = []

    try:
        # Step 1: First service call
        result_1 = call_service_1(data)
        completed_steps.append("step_1")

        # Step 2: Second service call
        result_2 = call_service_2(data, result_1)
        completed_steps.append("step_2")

        # Step 3: Third service call
        result_3 = call_service_3(data, result_2)
        completed_steps.append("step_3")

        return {"success": True, "data": result_3}

    except Exception as e:
        # Compensate in reverse order
        compensate(completed_steps, data)
        raise
```

## Scenario 1 — Purchase Flow

Steps and compensation:

```
1. ReserveSeat (gRPC)         → COMP: ReleaseSeat (gRPC)
2. Publish TTL to RabbitMQ    → COMP: ReleaseSeat (gRPC) — DLX is a backup
3. Deduct Credits (REST)      → COMP: Refund Credits (REST)
4. Create Order (REST)        → COMP: Update Order → FAILED (REST)
5. ConfirmSeat (gRPC)         → COMP: Refund Credits + Update Order → FAILED
6. Generate QR                → No compensation needed (read-only)
```

**Key:** If the user is `is_flagged = true`, insert OTP verification between step 2 and step 3.

## Scenario 2 — Transfer Flow

```
1. Validate (ownership, credits, no dup transfer)  → No side effects
2. Create Transfer record (REST)                    → COMP: Set → FAILED
3. Send OTPs to both parties (REST)                 → No COMP needed
4. Verify both OTPs (REST)                          → Allow 3 retries
5. Credit Transfer: buyer → seller (REST)           → COMP: Reverse credit transfer
6. UpdateOwner: seller → buyer (gRPC)               → COMP: Reverse credit + UpdateOwner back
7. Update Transfer → COMPLETED (REST)               → Log critical if fails (data consistent)
8. Generate new QR for buyer                        → Old QRs auto-invalidated (user_id mismatch)
```

## Scenario 3 — Verification Flow (read-heavy)

```
1. Decrypt QR payload (local)
2. Validate timestamp (local) — 60-second TTL
3. Fan out PARALLEL calls:
   a. VerifyTicket (gRPC) → seat status, owner, event_id
   b. GET /orders?seat_id= (REST) → confirm CONFIRMED order
   c. GET /events/{event_id} (REST) → expected hall_id
4. Run business rule checks
5. MarkCheckedIn (gRPC) — only write operation
6. Write entry_log — non-critical, log errors but don't fail
```

Use `asyncio.gather()` or `concurrent.futures.ThreadPoolExecutor` for the parallel fan-out in step 3.

## Service Client Setup

```python
# gRPC client
import grpc
from src.proto import inventory_pb2, inventory_pb2_grpc

channel = grpc.insecure_channel(os.environ["INVENTORY_SERVICE_URL"])
inventory_stub = inventory_pb2_grpc.InventoryServiceStub(channel)

# REST clients (httpx recommended for async, requests for sync)
import httpx

USER_SVC = os.environ["USER_SERVICE_URL"]
ORDER_SVC = os.environ["ORDER_SERVICE_URL"]
EVENT_SVC = os.environ["EVENT_SERVICE_URL"]
```

## Correlation ID Pattern

```python
import uuid

def generate_correlation_id():
    return str(uuid.uuid4())

# Attach to REST calls
headers = {"X-Correlation-ID": correlation_id}
httpx.get(f"{USER_SVC}/users/{user_id}", headers=headers)

# Attach to gRPC calls
metadata = [("correlation-id", correlation_id)]
inventory_stub.ReserveSeat(request, metadata=metadata)
```

## References

- `INSTRUCTIONS.md` Sections 5, 6, 7 — Full scenario flows with compensation matrices
- `API.md` — Request/response contracts for each endpoint
- `TASKS.md` Phase 7 — Full orchestrator implementation checklist
