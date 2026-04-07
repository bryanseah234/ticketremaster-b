# TicketRemaster Beyond-The-Labs (BTL) Report

## What This File Means

This file explains which parts of the backend are genuinely "beyond the labs".

I treated the following as **already covered in class**, so they are **not counted as standalone BTL claims**:

- Python + Flask REST services
- Flask-SQLAlchemy and database CRUD
- Postman testing
- basic synchronous HTTP between services
- basic RabbitMQ usage
- OutSystems as a low-code platform
- Docker and Docker Compose
- Kong as a basic API gateway
- Prometheus and Grafana

That means this BTL report focuses on the things the current backend uses that go past the lab baseline, either because they are new technologies or because they use a much deeper production-style pattern than what was taught.

## Executive Summary

The current backend contains **eight BTL-worthy items**:

1. gRPC and Protocol Buffers for seat-inventory RPC
2. Redis for distributed workflow state, locks, TTL data, and token revocation
3. Socket.IO WebSockets with Redis Pub/Sub for realtime fan-out
4. Advanced RabbitMQ patterns such as TTL queues, dead-letter exchanges, and timeout workers
5. Kubernetes deployment design using namespaces, StatefulSets, NetworkPolicies, and Kustomize
6. Cloudflare Tunnel for zero-trust public exposure of the local cluster
7. Advanced Kong usage through DB-less declarative config, route-level plugins, and edge policy composition
8. Saga-style compensation and idempotency patterns for distributed workflows

## Quick Table

| BTL item | Why it is beyond the labs | Main repo locations |
| --- | --- | --- |
| gRPC + Protocol Buffers | We did not learn internal RPC contracts in class | `proto/`, `services/seat-inventory-service/`, `orchestrators/ticket-purchase-orchestrator/` |
| Redis workflow state | We did not learn Redis locks, TTL caches, or token blacklists in class | `shared/token_blacklist.py`, `services/otp-wrapper/routes.py`, `orchestrators/ticket-verification-orchestrator/routes.py`, `services/seat-inventory-service/grpc_server.py` |
| Socket.IO + Redis Pub/Sub | We did not learn realtime WebSocket push in class | `services/notification-service/` |
| Advanced RabbitMQ patterns | Class covered messaging, but not TTL queues, DLX, timeout consumers, and compensation logging | `shared/queue_setup.py`, `orchestrators/ticket-purchase-orchestrator/`, `orchestrators/transfer-orchestrator/` |
| Kubernetes architecture | Class covered Docker and Compose, not Kubernetes runtime design | `k8s/base/` |
| Cloudflare Tunnel | Not covered in class | `k8s/base/edge-workloads.yaml`, `k8s/base/network-policies.yaml` |
| Advanced Kong policy | Class covered gateway basics, but this repo goes further with declarative route policy | `k8s/base/configuration.yaml`, `api-gateway/kong.yml.template` |
| Saga + idempotency | Not taught as a distributed workflow pattern in the labs | `orchestrators/ticket-purchase-orchestrator/routes.py`, `orchestrators/transfer-orchestrator/routes.py`, `orchestrators/credit-orchestrator/routes.py`, `services/seat-inventory-service/grpc_server.py` |

---

## BTL #1: gRPC and Protocol Buffers

**Simple explanation:**
If normal REST is like sending a letter with a lot of words, gRPC is like using a very short, fixed form over a direct hotline. It is faster and stricter.

**Why this is beyond the labs:**
The lab path used REST APIs everywhere. This repo adds an internal RPC contract for the most timing-sensitive part of the system: seat state changes during checkout.

**Where it exists in this repo:**

- contract: `proto/seat_inventory.proto`
- generated shared stubs: `shared/grpc/seat_inventory_pb2.py`, `shared/grpc/seat_inventory_pb2_grpc.py`
- gRPC server: `services/seat-inventory-service/server.py`
- gRPC business logic: `services/seat-inventory-service/grpc_server.py`
- gRPC client usage: `orchestrators/ticket-purchase-orchestrator/routes.py`
- expiry consumer using the same RPC contract: `orchestrators/ticket-purchase-orchestrator/dlx_consumer.py`

**Role in the codebase:**

- `ticket-purchase-orchestrator` uses gRPC to call `HoldSeat`, `ReleaseSeat`, `SellSeat`, and `GetSeatStatus`
- the purchase flow uses this because seat availability is the part most likely to break under concurrency
- the orchestrator also keeps a small gRPC channel pool so it does not create a fresh connection every time

**Why the design makes sense:**
Seat reservation is where double-booking risk lives. gRPC gives the repo a strict contract and lower overhead for that hot path, while the rest of the platform can stay on ordinary HTTP.

**Read more:**

- [gRPC overview](https://grpc.io/docs/what-is-grpc/)
- [Protocol Buffers overview](https://protobuf.dev/overview/)

---

## BTL #2: Redis for Workflow State, Locks, TTLs, and Token Revocation

**Simple explanation:**
Redis is like a very fast sticky-note board. We use it for things that should be remembered briefly, not forever.

**Why this is beyond the labs:**
The lab material did not cover Redis, distributed locks, token blacklists, or TTL-backed workflow helpers.

**Where it exists in this repo:**

- JWT revocation blacklist: `shared/token_blacklist.py`
- OTP rate limiting: `services/otp-wrapper/routes.py`
- distributed scan lock: `orchestrators/ticket-verification-orchestrator/routes.py`
- seat hold cache and idempotency cache: `services/seat-inventory-service/grpc_server.py`
- purchase confirmation cache read and Redis circuit breaker: `orchestrators/ticket-purchase-orchestrator/routes.py`

**Role in the codebase:**

- stores revoked JWTs until they expire naturally
- stores OTP attempt counters and temporary account lockouts
- prevents two staff devices from checking in the same ticket at the same moment
- caches short-lived seat hold state so purchase confirmation does not always need to re-fetch from the database
- stores idempotency results for release operations

**Why the design makes sense:**
This repo does **not** use Redis as the main database. It uses Redis only for "fast temporary memory" jobs:

- short timers
- retry protection
- lock ownership
- quick state checks

That is exactly the kind of problem Redis is good at.

**Read more:**

- [Redis docs](https://redis.io/docs/latest/)
- [Redis Pub/Sub](https://redis.io/docs/latest/develop/pubsub/)

---

## BTL #3: Socket.IO WebSockets with Redis Pub/Sub

**Simple explanation:**
A REST API is like asking, "Any news yet?" again and again.
A WebSocket is like leaving the phone call open so the server can say, "News just happened."

**Why this is beyond the labs:**
The labs did not cover realtime browser push, WebSockets, or cross-instance event broadcasting.

**Where it exists in this repo:**

- implementation: `services/notification-service/app.py`
- usage notes: `services/notification-service/NOTIFICATIONS.md`
- service README: `services/notification-service/README.md`

**Role in the codebase:**

- clients connect through Socket.IO
- clients subscribe to event channels such as `seat_update`, `ticket_update`, and `transfer_update`
- services can push an internal HTTP request to the notification service
- the notification service republishes the event to Redis Pub/Sub
- connected clients get the update immediately

**Why the design makes sense:**
RabbitMQ is good for background work between backend components.
WebSockets are good for telling the frontend "something changed right now".
This repo uses both, because they solve different problems.

**Read more:**

- [Socket.IO docs](https://socket.io/docs/v4/)
- [Redis Pub/Sub](https://redis.io/docs/latest/develop/pubsub/)

---

## BTL #4: Advanced RabbitMQ Patterns

**Simple explanation:**
Basic queues are like "do this job later".
This repo goes further and says things like:

- "do this if the timer expires"
- "send this somewhere else if it expires"
- "cancel this workflow automatically after 24 hours"

**Why this is beyond the labs:**
RabbitMQ itself was learned in class, but this repo uses more advanced broker behavior than a normal producer-consumer example.

**Where it exists in this repo:**

- queue topology: `shared/queue_setup.py`
- hold expiry publisher: `orchestrators/ticket-purchase-orchestrator/routes.py`
- hold expiry consumer: `orchestrators/ticket-purchase-orchestrator/dlx_consumer.py`
- seller notification publisher: `orchestrators/transfer-orchestrator/routes.py`
- transfer timeout publisher: `orchestrators/transfer-orchestrator/routes.py`
- seller notification consumer: `orchestrators/transfer-orchestrator/seller_consumer.py`
- transfer timeout consumer: `orchestrators/transfer-orchestrator/timeout_consumer.py`

**Role in the codebase:**

- `seat_hold_ttl_queue` holds seat-expiry messages for the purchase flow
- when the message expires, it is routed into `seat_hold_expired_queue` through a dead-letter exchange
- a consumer then releases the seat automatically
- `seller_notification_queue` decouples seller notification work from the live buyer request
- `transfer_timeout_queue` auto-cancels incomplete transfers after the configured timeout

**Why the design makes sense:**
It stops long-running workflows from depending on a single user keeping a browser tab open. The queue system remembers what must happen later even if the original request is already over.

**Read more:**

- [RabbitMQ TTL](https://www.rabbitmq.com/docs/ttl)
- [RabbitMQ Dead Letter Exchanges](https://www.rabbitmq.com/docs/dlx)

---

## BTL #5: Kubernetes Runtime Design

**Simple explanation:**
If Docker containers are like packed lunchboxes, Kubernetes is the school system that decides where every lunchbox goes, restarts it if it falls, and keeps teams separate.

**Why this is beyond the labs:**
The labs covered Docker and Docker Compose. This repo is maintained primarily as a Kubernetes system.

**Where it exists in this repo:**

- entrypoint manifests: `k8s/base/`
- namespaces: `k8s/base/namespaces.yaml`
- network isolation: `k8s/base/network-policies.yaml`
- data workloads: `k8s/base/data-plane.yaml`
- core workloads: `k8s/base/core-workloads.yaml`
- edge workloads: `k8s/base/edge-workloads.yaml`
- kustomization: `k8s/base/kustomization.yaml`

**Role in the codebase:**

- separates the system into `ticketremaster-edge`, `ticketremaster-core`, and `ticketremaster-data`
- runs PostgreSQL as StatefulSets because database pods need stable identity and storage
- uses NetworkPolicies so not every pod can talk to every other pod
- mounts Kong's declarative config through a ConfigMap
- uses readiness/liveness probes so unhealthy workloads can be detected
- includes seed jobs as part of normal environment bring-up

**Why the design makes sense:**
This layout turns the repo from "a bunch of containers" into a structured platform:

- edge handles ingress
- core handles business logic
- data handles stateful infrastructure

That layering is a real architecture decision, not just a deployment detail.

**Read more:**

- [Kubernetes overview](https://kubernetes.io/docs/concepts/overview/)
- [Namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/)
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)

---

## BTL #6: Cloudflare Tunnel

**Simple explanation:**
Instead of opening your house to the whole street, Cloudflare Tunnel is like having the house call Cloudflare first and say, "If anyone needs me, send them through you."

**Why this is beyond the labs:**
Cloudflare Tunnel and zero-trust exposure were not part of the lab stack.

**Where it exists in this repo:**

- deployment: `k8s/base/edge-workloads.yaml`
- edge restrictions: `k8s/base/network-policies.yaml`
- startup support: `start-backend.bat`, `scripts/start_k8s.ps1`

**Role in the codebase:**

- exposes the local Kubernetes-backed gateway through `https://ticketremasterapi.hong-yi.me`
- avoids needing a public IP on Minikube
- keeps the cluster on an outbound-only connection model
- lets the backend maintainer share a live environment for smoke testing

**Why the design makes sense:**
This is a very practical team-maintenance choice. It gives the repo a public URL without turning the local machine into a traditionally exposed server.

**Read more:**

- [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)

---

## BTL #7: Advanced Kong Usage

**Simple explanation:**
Kong is the front desk of the system. But in this repo it is not just forwarding calls. It is also checking keys, limiting traffic, handling CORS, and keeping route behavior consistent.

**Why this is only partly beyond the labs:**
Kong itself was taught in class. What makes it BTL here is the **deeper production-style usage**, not the fact that Kong exists.

**Where it exists in this repo:**

- local template: `api-gateway/kong.yml.template`
- Kubernetes source of truth: `k8s/base/configuration.yaml`

**Role in the codebase:**

- runs in DB-less declarative mode
- applies global plugins like CORS and rate limiting
- adds route-level `key-auth` only where needed
- supports both current no-prefix routes and `/api/...` compatibility routes
- protects browser-facing microservices from being called directly

**Why the design makes sense:**
It keeps authentication and edge policy consistent in one place. That way each orchestrator can focus on business logic instead of repeating gateway concerns.

**Read more:**

- [Kong Gateway docs](https://developer.konghq.com/gateway/)
- [Kong key-auth plugin](https://developer.konghq.com/plugins/key-auth/)

---

## BTL #8: Saga Compensation and Idempotency

**Simple explanation:**
If a workflow has many steps and step 4 fails, we need a plan for how to undo steps 1 to 3 safely.
That plan is a **saga**.
If the same request arrives twice, we should not charge twice.
That protection is **idempotency**.

**Why this is beyond the labs:**
The lab summary did not cover saga orchestration, compensation, replay protection, or idempotent distributed workflow design.

**Where it exists in this repo:**

- purchase compensation: `orchestrators/ticket-purchase-orchestrator/routes.py`
- transfer saga: `orchestrators/transfer-orchestrator/routes.py`
- Stripe webhook idempotency: `orchestrators/credit-orchestrator/routes.py`
- seat release idempotency: `services/seat-inventory-service/grpc_server.py`

**Role in the codebase:**

- purchase confirmation can compensate when seat sale succeeds but ticketing or credit deduction fails
- transfer completion uses a multi-step saga across OutSystems, credit ledger, ticket ownership, and listing state
- Stripe webhook processing checks existing references before applying balance changes again
- seat release caches a previous result to prevent duplicate release side effects

**Why the design makes sense:**
In a distributed system, failures happen halfway through. The codebase already assumes this and includes recovery logic, instead of pretending every multi-step workflow is one perfectly atomic action.

**Read more:**

- [Idempotency (Stripe docs)](https://docs.stripe.com/api/idempotent_requests)
- [Saga pattern overview](https://microservices.io/patterns/data/saga.html)

---

## Final Conclusion

The strongest BTL items in this backend are:

- gRPC for seat inventory
- Redis for locks, TTL state, and token revocation
- realtime WebSocket push
- Kubernetes runtime design
- Cloudflare Tunnel

The repo also shows important beyond-lab **engineering patterns**:

- advanced RabbitMQ usage
- advanced Kong policy design
- saga and idempotency handling

So the backend is not just "more Flask services". It is a more production-like distributed system than the lab baseline, with extra infrastructure, stronger workflow control, and more careful failure handling.
