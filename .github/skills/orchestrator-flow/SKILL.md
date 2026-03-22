---
name: orchestrator-flow
description: Repo-specific saga pattern for TicketRemaster orchestrators, including purchase, transfer, and verification coordination with compensation behavior.
---

# Orchestrator Flow Pattern

## When to Use

Use this skill when implementing or modifying multi-step flows in `orchestrators/*`.

## Architecture Rules

1. Keep orchestrators stateless and side-effect ordering explicit.
2. Every mutating step should have a compensation strategy.
3. Use gRPC for Seat Inventory calls and REST for other services/wrappers.
4. Use RabbitMQ TTL/DLX for seat-hold timeout safety nets.
5. Keep auth middleware centralized and avoid duplicate logic across orchestrators.

## Flow Template

```python
def execute_flow(data: dict) -> dict:
    completed_steps = []
    try:
        step_1(data); completed_steps.append("step_1")
        step_2(data); completed_steps.append("step_2")
        step_3(data); completed_steps.append("step_3")
        return {"ok": True}
    except Exception:
        compensate(completed_steps, data)
        raise
```

## Purchase Flow

Steps and compensation:

```
1. Hold seat (gRPC)                      -> COMP: Release seat
2. Publish hold TTL to queue             -> COMP: Release seat
3. Deduct balance / top-up confirmation  -> COMP: Reverse balance operation
4. Log credit transaction                -> COMP: Write reversal transaction when required
5. Confirm seat as sold (gRPC)           -> COMP: Reverse previous side effects
6. Create ticket record                  -> COMP: Mark failed and reverse prior state
```

## Transfer Flow

Typical sequence:

```
1. Validate ownership and transfer eligibility
2. Create transfer state record
3. Send and verify buyer/seller OTP
4. Apply value transfer
5. Move ticket ownership
6. Mark transfer completed
```

## Verification Flow

Typical sequence:

```
1. Decrypt QR payload
2. Check QR TTL
3. Validate seat status and owner
4. Validate venue/hall context
5. Detect duplicate scan
6. Write check-in + audit log
```

## Correlation ID Pattern
Use the QR skill for cryptographic and validation specifics:
[../qr-encryption/SKILL.md](../qr-encryption/SKILL.md)

## References

- [../../../orchestrators/README.md](../../../orchestrators/README.md)
- [../../../TASK.md](../../../TASK.md)
- [../../../INSTRUCTION.md](../../../INSTRUCTION.md)
- [../error-handling/SKILL.md](../error-handling/SKILL.md)
- [../grpc-service/SKILL.md](../grpc-service/SKILL.md)
