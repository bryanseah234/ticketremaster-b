# TICKETREMASTER K8S ARCHITECTURE

This document summarizes the Kubernetes architecture for the TicketRemaster backend.

## Namespaces

- `ticketremaster-edge` — ingress and API gateway boundary
- `ticketremaster-core` — orchestrators, services, and jobs
- `ticketremaster-data` — PostgreSQL, Redis, RabbitMQ

## Edge Layer

Primary components:
- `cloudflared`
- `kong` (proxy + admin)

Responsibilities:
- Ingress control
- Route mapping to orchestrators
- Cross-cutting auth/rate-limit policy

## Core Layer

Contains:
- Browser-facing orchestrators (ports 8100–8108)
- Atomic backend services and wrappers
- Seeding and migration jobs

Responsibilities:
- Business workflow orchestration
- Service-to-service REST/gRPC communication
- Integration with external credit provider and wrappers

## Data Layer

Contains:
- Service-scoped PostgreSQL StatefulSets
- Redis for caching/publish-subscribe use cases
- RabbitMQ for asynchronous workflows

Responsibilities:
- Durable state and queue persistence
- Isolation of data ownership by service boundary

## Deployment Model

Local workflow:

```bash
kubectl kustomize k8s/base
kubectl apply -k k8s/base
```

Post-deploy checks:

```bash
kubectl get pods -n ticketremaster-edge
kubectl get pods -n ticketremaster-core
kubectl get pods -n ticketremaster-data
kubectl get svc -n ticketremaster-core
```

## Operational Notes

- Kong is the only supported public ingress path.
- Stateful components should not be directly internet-exposed.
- Service-to-service communication remains private within the cluster network.

## Related Documentation

- [README.md](README.md)
- [COMPLETE_SYSTEM_DOCUMENTATION.md](COMPLETE_SYSTEM_DOCUMENTATION.md)
- [TESTING.md](TESTING.md)
- [INSTRUCTION.md](INSTRUCTION.md)
