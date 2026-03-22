# ticket-purchase-orchestrator

Ticket Purchase Orchestrator coordinates the paid checkout flow: seat hold, payment/credit validation, seat confirmation, ticket issuance, and compensation handling.

## Current Status

- Folder exists as a planned orchestrator module.
- Runtime implementation is not complete yet.
- Queue setup helper exists in this folder as a starting point.

## Planned Frontend-Facing Endpoints

- `POST /purchase/hold/<inventory_id>`
- `POST /purchase/confirm/<inventory_id>`

Source contract: [../../FRONTEND.md](../../FRONTEND.md).

## Downstream Dependencies

- `seat-inventory-service` (gRPC) for hold/release/sell transitions
- RabbitMQ for hold TTL and expiry fallback
- OutSystems credit service for deduction
- `credit-transaction-service` for ledger
- `ticket-service` for ticket creation

## Intended Saga Flow

1. Hold seat via gRPC.
2. Publish hold expiry metadata to queue.
3. Deduct credits.
4. Create credit transaction.
5. Confirm seat as sold via gRPC.
6. Create ticket record.
7. Return purchase response with ticket information.

Compensation reverses completed side effects in reverse order when any step fails.

## Implementation Notes

- Include startup queue declaration and DLX consumer lifecycle.
- Use strict timeout/error mapping for all downstream calls.
- Keep idempotency keys for confirm endpoint to avoid duplicate charges/tickets.

## Related Docs

- Orchestrator index: [../README.md](../README.md)
- RabbitMQ and orchestrator sequence: [../../INSTRUCTION.md](../../INSTRUCTION.md)
- Task checklist itemization: [../../TASK.md](../../TASK.md)
- Shared gRPC stubs: [../../shared/grpc/README.md](../../shared/grpc/README.md)
- Orchestration playbook: [../../.github/skills/orchestrator-flow/SKILL.md](../../.github/skills/orchestrator-flow/SKILL.md)

