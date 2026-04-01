# TASK

This checklist tracks high-level backend implementation and stabilization work.

## Phase 1 — Core Runtime Baseline

- [ ] Ensure all orchestrators have runnable `app.py` and `routes.py`
- [ ] Confirm health endpoints are exposed and routed via Kong
- [ ] Verify environment variable defaults across services

## Phase 2 — Data and Contract Integrity

- [ ] Run migrations for all service databases
- [ ] Re-seed deterministic local data
- [ ] Validate gRPC contract compatibility for seat inventory stubs

## Phase 3 — Workflow Completion

- [ ] Purchase flow: hold → confirm → ticket issuance
- [ ] Transfer flow: initiate → OTP verify → ownership update
- [ ] Verification flow: scan → validate → audit log write
- [ ] Marketplace flow: list → browse → cancel/complete

## Phase 4 — Reliability and Async

- [ ] RabbitMQ queues are declared at startup
- [ ] Seat hold expiry handling is idempotent
- [ ] Notification fan-out path is validated
- [ ] Retry/failure paths are observable in logs

## Phase 5 — Quality Gates

- [ ] `pytest` passes
- [ ] Postman/Newman collection passes for critical flows
- [ ] Swagger UIs reachable for all orchestrators
- [ ] Kubernetes manifests validate via `kubectl kustomize k8s/base`

## References

- [README.md](README.md)
- [TESTING.md](TESTING.md)
- [INSTRUCTION.md](INSTRUCTION.md)
- [orchestrators/README.md](orchestrators/README.md)
