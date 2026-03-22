# Shared Project Assets

This folder stores reusable assets that are copied into services/orchestrators during implementation.

## Contents

- `requirements.txt` — baseline Python dependency set used as a starting point for new modules
- `grpc/` — generated Seat Inventory gRPC Python stubs shared across modules that call inventory RPCs

## Usage Rules

- Treat files here as source templates, then copy into module-local folders.
- Keep module-specific dependencies in each module's own `requirements.txt`.
- Regenerate gRPC files from `proto/seat_inventory.proto` before copying if proto contracts change.

## Common Consumers

- `services/seat-inventory-service`
- `orchestrators/ticket-purchase-orchestrator`
- `orchestrators/transfer-orchestrator`
- `orchestrators/ticket-verification-orchestrator`

## Related Docs

- gRPC copy/regeneration notes: [grpc/README.md](grpc/README.md)
- Scaffolding templates: [../templates/README.md](../templates/README.md)
- Service index: [../services/README.md](../services/README.md)
- Orchestrator index: [../orchestrators/README.md](../orchestrators/README.md)
