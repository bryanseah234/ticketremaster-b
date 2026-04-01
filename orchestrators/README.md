# Orchestrators Index

This folder contains orchestration-layer services that coordinate multi-step flows across atomic services and wrappers.

Current repository status:
- All orchestrator folders and README plans exist.
- Most orchestrator runtime files are still to be implemented.
- `ticket-purchase-orchestrator` and `transfer-orchestrator` already include startup queue setup helpers.

## Navigation

### Orchestrator modules
- [auth-orchestrator/README.md](auth-orchestrator/README.md) — login, JWT issuance, role claims
- [event-orchestrator/README.md](event-orchestrator/README.md) — event browse aggregation
- [credit-orchestrator/README.md](credit-orchestrator/README.md) — balance, top-up initiate, Stripe webhook
- [ticket-purchase-orchestrator/README.md](ticket-purchase-orchestrator/README.md) — hold, confirm, compensation, TTL handling
- [qr-orchestrator/README.md](qr-orchestrator/README.md) — QR refresh/generation
- [marketplace-orchestrator/README.md](marketplace-orchestrator/README.md) — list, browse, cancel listing
- [transfer-orchestrator/README.md](transfer-orchestrator/README.md) — buyer/seller OTP transfer flow
- [ticket-verification-orchestrator/README.md](ticket-verification-orchestrator/README.md) — staff scan validation

### Shared scaffolding docs
- [../templates/README.md](../templates/README.md)
- [../shared/README.md](../shared/README.md)
- [../shared/grpc/README.md](../shared/grpc/README.md)

### Internal implementation playbooks
- Workspace skill index and agent workflow guidance: [../AGENTS.md#available-skills](../AGENTS.md#available-skills)
- Recommended relevant skills for this folder: `orchestrator-flow`, `flask-service`, `error-handling`, `qr-encryption`

## Standard Build Expectations

Each orchestrator should include:
- `app.py`
- `routes.py`
- `middleware.py`
- `requirements.txt`
- `Dockerfile`

For orchestrators using seat operations:
- copy gRPC stubs from `shared/grpc/`
- include `grpcio` and `grpcio-tools` dependencies

For orchestrators using queue expiry/compensation:
- include startup queue declaration
- start a background consumer thread safely

## Related Docs

- Implementation sequence and dependency rules: [../INSTRUCTION.md](../INSTRUCTION.md)
- Orchestrator task checklist by phase: [../TASK.md](../TASK.md)
- Frontend-facing orchestrator API contract: [../FRONTEND.md](../FRONTEND.md)
- End-to-end testing flow: [../TESTING.md](../TESTING.md)
- Root documentation hub: [../README.md](../README.md)
