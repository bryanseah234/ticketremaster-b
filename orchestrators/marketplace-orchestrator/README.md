# marketplace-orchestrator

Marketplace Orchestrator coordinates listing creation, listing cancellation, and public marketplace browse flows.

## Current Status

- Folder exists as a planned orchestrator module.
- Runtime implementation files are not built yet.
- This README captures target flow boundaries and service ownership.

## Planned Frontend-Facing Endpoints

- `GET /marketplace`
- `POST /marketplace/list`
- `DELETE /marketplace/<listing_id>`

Source contract: [../../FRONTEND.md](../../FRONTEND.md).

## Downstream Dependencies

- `marketplace-service` for listing state
- `ticket-service` for ticket ownership and active status checks
- `seat-inventory-service` for availability state if needed
- auth middleware for seller identity

## Flow Responsibilities

- validate that caller owns the ticket before listing
- ensure no conflicting active listing exists
- enforce status transitions through orchestrator logic
- expose read model suitable for frontend marketplace screens

## Related Docs

- Orchestrator index: [../README.md](../README.md)
- Marketplace atomic service: [../../services/marketplace-service/README.md](../../services/marketplace-service/README.md)
- Ticket atomic service: [../../services/ticket-service/README.md](../../services/ticket-service/README.md)
- Build and task order: [../../TASK.md](../../TASK.md)
- Saga flow reference: [../../.github/skills/orchestrator-flow/SKILL.md](../../.github/skills/orchestrator-flow/SKILL.md)

