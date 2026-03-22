# TicketRemaster Backend

TicketRemaster is a Python microservices backend for ticketing, transfer, payments, OTP verification, and event operations.  
This repository contains:
- Atomic Flask services with isolated PostgreSQL databases
- External wrappers (Stripe and SMU Notification OTP)
- RabbitMQ runtime checks and queue setup helpers
- Shared Postman assets for end-to-end verification

## Documentation Hub

Use this section as the starting point. All major docs are cross-linked below.

### Project-level docs
- [TESTING.md](TESTING.md) — full testing playbook, Postman flow, external integration checks, troubleshooting
- [DESIGN.md](DESIGN.md) — architecture and design context
- [INSTRUCTION.md](INSTRUCTION.md) — implementation guide and engineering rules
- [TASK.md](TASK.md) — phase-by-phase execution checklist and status
- [FRONTEND.md](FRONTEND.md) — frontend contract and orchestrator-facing API plan
- [OUTSYSTEMS.md](OUTSYSTEMS.md) — OutSystems integration reference

### Collections and environments
- [postman/README.md](postman/README.md) — Postman asset usage, seeded-variable assumptions, and chaining notes
- [postman/TicketRemaster.postman_collection.json](postman/TicketRemaster.postman_collection.json) — shared collection
- [postman/TicketRemaster.local.postman_environment.json](postman/TicketRemaster.local.postman_environment.json) — local environment

### Service-level docs
- [services/README.md](services/README.md) — service index and where each service guide lives
- [services/user-service/README.md](services/user-service/README.md)
- [services/venue-service/README.md](services/venue-service/README.md)
- [services/seat-service/README.md](services/seat-service/README.md)
- [services/event-service/README.md](services/event-service/README.md)
- [services/seat-inventory-service/README.md](services/seat-inventory-service/README.md)
- [services/ticket-service/README.md](services/ticket-service/README.md)
- [services/ticket-log-service/README.md](services/ticket-log-service/README.md)
- [services/marketplace-service/README.md](services/marketplace-service/README.md)
- [services/transfer-service/README.md](services/transfer-service/README.md)
- [services/credit-transaction-service/README.md](services/credit-transaction-service/README.md)
- [services/stripe-wrapper/README.md](services/stripe-wrapper/README.md)
- [services/otp-wrapper/README.md](services/otp-wrapper/README.md)

### Orchestrator docs
- [orchestrators/README.md](orchestrators/README.md) — orchestrator index and implementation status
- [orchestrators/auth-orchestrator/README.md](orchestrators/auth-orchestrator/README.md)
- [orchestrators/event-orchestrator/README.md](orchestrators/event-orchestrator/README.md)
- [orchestrators/credit-orchestrator/README.md](orchestrators/credit-orchestrator/README.md)
- [orchestrators/ticket-purchase-orchestrator/README.md](orchestrators/ticket-purchase-orchestrator/README.md)
- [orchestrators/qr-orchestrator/README.md](orchestrators/qr-orchestrator/README.md)
- [orchestrators/marketplace-orchestrator/README.md](orchestrators/marketplace-orchestrator/README.md)
- [orchestrators/transfer-orchestrator/README.md](orchestrators/transfer-orchestrator/README.md)
- [orchestrators/ticket-verification-orchestrator/README.md](orchestrators/ticket-verification-orchestrator/README.md)

### Shared scaffolding docs
- [templates/README.md](templates/README.md) — Dockerfile scaffolding templates and copy map
- [shared/README.md](shared/README.md) — reusable dependencies and generated artifacts
- [shared/grpc/README.md](shared/grpc/README.md) — gRPC stub generation and copy rules

### Internal implementation skills
- [.github/skills/flask-service/SKILL.md](.github/skills/flask-service/SKILL.md)
- [.github/skills/orchestrator-flow/SKILL.md](.github/skills/orchestrator-flow/SKILL.md)
- [.github/skills/grpc-service/SKILL.md](.github/skills/grpc-service/SKILL.md)
- [.github/skills/database-models/SKILL.md](.github/skills/database-models/SKILL.md)
- [.github/skills/error-handling/SKILL.md](.github/skills/error-handling/SKILL.md)
- [.github/skills/qr-encryption/SKILL.md](.github/skills/qr-encryption/SKILL.md)

## Stripe and OTP Quick Navigation

- Stripe manual/automated testing: [TESTING.md](TESTING.md) and [services/stripe-wrapper/README.md](services/stripe-wrapper/README.md)
- OTP manual/automated testing: [TESTING.md](TESTING.md) and [services/otp-wrapper/README.md](services/otp-wrapper/README.md)

## Recommended Reading Order

1. [TESTING.md](TESTING.md)  
2. [postman/README.md](postman/README.md)  
3. [services/README.md](services/README.md)  
4. [services/stripe-wrapper/README.md](services/stripe-wrapper/README.md) and [services/otp-wrapper/README.md](services/otp-wrapper/README.md)  
5. [TASK.md](TASK.md) and [INSTRUCTION.md](INSTRUCTION.md)
