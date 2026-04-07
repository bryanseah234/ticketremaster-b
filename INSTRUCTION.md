# TicketRemaster Engineering Notes

This document explains the current design logic of the backend codebase.

## Core architectural decisions

### 1. Kubernetes-first runtime

The maintained system-level environment is the Minikube stack under `k8s/base`.

That means:

- Kong is the real browser ingress even in local development
- seed jobs are part of normal startup, not a separate manual step
- service DNS names in `ticketremaster-core` are the actual inter-service contract
- stateful dependencies live in `ticketremaster-data`

### 2. Orchestrator plus atomic-service split

The codebase separates:

- orchestrators, which own frontend-facing workflow composition and auth logic
- services, which own bounded-context data and narrow internal contracts

This keeps the browser surface stable while allowing internal service boundaries to stay small and explicit.

### 3. Service-owned persistence

Every stateful business service owns its own PostgreSQL database. No service should write directly into another service's database.

Why that matters:

- it keeps domain ownership clear
- it avoids cross-service migration coupling
- it makes failures easier to localize

### 4. External credit authority

OutSystems is the authority for credit balance. The internal `credit-transaction-service` is the ledger of platform-side credit movements, not the authoritative balance.

That split is intentional:

- OutSystems remains the financial record of balance
- the internal ledger gives TicketRemaster queryable audit history for purchase, top-up, and transfer flows

### 5. Mixed sync and async workflow model

TicketRemaster uses both immediate request/response composition and asynchronous messaging:

- synchronous HTTP between orchestrators and services for request-time operations
- gRPC for the latency-sensitive seat hold and sale path
- Redis for ephemeral hold cache and distributed lock support
- RabbitMQ for hold expiry, seller notifications, and timeout work

## Why specific components exist

### Kong

Kong centralizes:

- CORS
- key-auth for selected route groups
- basic rate limiting
- a consistent browser ingress surface

This lets individual services stay focused on gateway policy rather than duplicating it.

### `seat-inventory-service`

This service exists separately from `seat-service` because the physical seat definition and the event-specific seat state are different concerns.

- `seat-service` owns venue seat metadata
- `seat-inventory-service` owns event seat status such as `available`, `held`, and `sold`

### `ticket-log-service`

Duplicate staff scans are a workflow concern that depends on persistent scan history, so check-in logs live in a dedicated service instead of being embedded inside `ticket-service`.

### `notification-service`

Realtime fan-out is isolated so other services can publish domain events without each of them becoming a WebSocket host.

## Authentication and authorization model

- JWTs are minted by `auth-orchestrator`
- shared middleware in orchestrators validates JWTs
- staff authorization depends on `role=staff`
- venue-specific staff checks use `venueId` carried in the JWT
- Kong key-auth is additive to JWT on selected route groups

## Current route-shape principles

- browser routes are exposed through Kong only
- public browse surfaces stay public: `events`, `venues`, `marketplace`
- transactional routes are protected by JWT plus Kong key-auth
- admin routes use orchestrator-side JWT role checks
- staff verification routes are POST-only

## Startup design logic

The current maintained startup flow waits on real conditions, not fixed sleep windows:

- data StatefulSets must be ready
- core and edge Deployments must roll out successfully
- seed Jobs must complete
- Kong must answer on `localhost:8000`
- optional Cloudflare smoke checks wait for the public `/events` endpoint

This prevents the old failure mode where auth smoke tests ran before user-service or seed jobs were actually usable.

## Documentation map

- [README.md](README.md): top-level overview
- [LOCAL_DEV_SETUP.md](LOCAL_DEV_SETUP.md): maintainer setup
- [TESTING.md](TESTING.md): verification flow
- [API.md](API.md): route reference
- [FRONTEND.md](FRONTEND.md): frontend contract
- [services/README.md](services/README.md): service index
- [orchestrators/README.md](orchestrators/README.md): orchestrator index
