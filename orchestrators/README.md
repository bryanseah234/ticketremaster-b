# Orchestrators Index

This folder contains the browser-facing workflow layer of TicketRemaster.

## Current orchestrators

- [auth-orchestrator/README.md](auth-orchestrator/README.md)
- [event-orchestrator/README.md](event-orchestrator/README.md)
- [credit-orchestrator/README.md](credit-orchestrator/README.md)
- [ticket-purchase-orchestrator/README.md](ticket-purchase-orchestrator/README.md)
- [qr-orchestrator/README.md](qr-orchestrator/README.md)
- [marketplace-orchestrator/README.md](marketplace-orchestrator/README.md)
- [transfer-orchestrator/README.md](transfer-orchestrator/README.md)
- [ticket-verification-orchestrator/README.md](ticket-verification-orchestrator/README.md)

## Design role

Orchestrators:

- expose the routes that Kong sends browser traffic to
- enforce JWT role rules and workflow-level validation
- aggregate data from multiple services into frontend-friendly responses
- coordinate cross-service sagas such as purchase, top-up, transfer, and staff verification

They do not own persistent business databases.

## Shared patterns

- shared JWT middleware
- shared internal HTTP client helpers
- service-to-service timeouts
- consistent error envelope shape
- explicit compensation when a cross-service workflow partially fails

## Related docs

- [../README.md](../README.md)
- [../API.md](../API.md)
- [../FRONTEND.md](../FRONTEND.md)
- [../INSTRUCTION.md](../INSTRUCTION.md)
