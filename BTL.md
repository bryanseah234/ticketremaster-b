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
If normal REST is like sending a letter with a lot of words, gRPC is like using a short fixed form over a direct hotline. It is stricter, more explicit, and better suited to fast internal service-to-service calls.

**Why this is beyond the labs:**
The lab path used REST APIs everywhere. This repo adds an internal RPC contract for the most timing-sensitive part of the system: seat state changes during checkout.

**How it works in this repo:**

- `proto/seat_inventory.proto` defines a strict service contract for `HoldSeat`, `ReleaseSeat`, `SellSeat`, and `GetSeatStatus`
- generated stubs in `shared/grpc/` give both server and client code the same message definitions
- `seat-inventory-service` runs a gRPC server alongside its Flask app
- `ticket-purchase-orchestrator` calls that gRPC service for hold, release, sell, and status checks during checkout
- the seat-hold expiry consumer also reuses the same gRPC contract to release seats automatically when TTL messages expire

**Why we chose gRPC here:**

- seat reservation is the most concurrency-sensitive path in the backend
- the seat inventory flow benefits from a strict typed contract rather than loosely shaped JSON
- gRPC reduces protocol overhead on a hot internal path without forcing the whole platform away from REST
- it lets the repo keep browser-facing APIs simple while optimizing only the part that most needs it

**What benefits it gives us compared to other options:**

- compared to using REST everywhere:
  - gRPC gives a more rigid contract for the seat lifecycle calls
  - it is a better fit for low-latency internal RPC than repeatedly exchanging JSON over HTTP on the same hot path
  - it makes the seat operations feel like a dedicated internal capability rather than just another public-style REST endpoint
- compared to moving everything to gRPC:
  - the repo keeps gRPC limited to one high-value internal path instead of adding protocol complexity to every service
  - browser-facing workflows can remain ordinary Flask REST APIs behind Kong
- compared to direct database sharing between orchestrator and service:
  - the orchestrator does not need to bypass service boundaries just to reserve a seat
  - seat state remains owned by `seat-inventory-service`

**Where it exists in this repo:**

- contract and generated code:
  - `proto/seat_inventory.proto`
  - `shared/grpc/seat_inventory_pb2.py`
  - `shared/grpc/seat_inventory_pb2_grpc.py`
  - `shared/grpc/README.md`
- server side:
  - `services/seat-inventory-service/server.py`
  - `services/seat-inventory-service/grpc_server.py`
  - `services/seat-inventory-service/README.md`
- client side:
  - `orchestrators/ticket-purchase-orchestrator/routes.py`
  - `orchestrators/ticket-purchase-orchestrator/dlx_consumer.py`

**Limitations and tradeoffs:**

- it adds another protocol to the backend, so the team has to maintain both REST and gRPC understanding
- the protobuf stubs have to stay in sync with the proto contract
- this is an internal optimization, not something the browser uses directly

**Presentation talking points:**

- "We did not replace REST everywhere. We used gRPC only for the seat inventory path, because that is where concurrency and double-booking risk are highest."
- "The main benefit is a stricter internal contract for hold, release, sell, and status checks."
- "This is beyond the labs because the class stack was REST-first, while this repo introduces a mixed-protocol design for performance-sensitive internal calls."

**Read more:**

- [gRPC overview](https://grpc.io/docs/what-is-grpc/)
- [Protocol Buffers overview](https://protobuf.dev/overview/)

---

## BTL #2: Redis for Workflow State, Locks, TTLs, and Token Revocation

**Simple explanation:**
Redis is like a very fast sticky-note board. We use it for things that should be remembered briefly, not forever.

**Why this is beyond the labs:**
The lab material did not cover Redis, distributed locks, token blacklists, or TTL-backed workflow helpers.

**How it works in this repo:**

- `shared/token_blacklist.py` stores revoked JWT identifiers in Redis until they expire naturally
- `services/otp-wrapper/routes.py` uses Redis TTL keys for OTP attempt counting and temporary lockouts
- `orchestrators/ticket-verification-orchestrator/routes.py` uses Redis distributed locks to reduce double-scan races at verification time
- `services/seat-inventory-service/grpc_server.py` uses Redis for short-lived hold caching and idempotency caching
- `orchestrators/ticket-purchase-orchestrator/routes.py` reads cached hold state and includes a Redis circuit-breaker path so Redis failures do not automatically collapse the whole purchase flow

**Why we chose Redis here:**

- these use cases all need fast temporary state, not permanent business storage
- Redis TTL support makes it a natural fit for expiring tokens, lock windows, cooldowns, and short workflow memory
- it helps coordinate behavior across multiple services and pods in a way in-process memory cannot
- it improves responsiveness for hot workflow checks without turning Redis into the system of record

**What benefits it gives us compared to other options:**

- compared to using only PostgreSQL for everything:
  - Redis is better suited to expiring keys, lightweight locks, and short-lived counters
  - it avoids turning workflow helpers into heavier database reads and writes
- compared to keeping this state only in local process memory:
  - local memory would not work properly across multiple containers or pods
  - Redis gives a shared coordination point for lock ownership, revocation state, and temporary workflow data
- compared to making everything permanent:
  - these values are supposed to disappear automatically after a short period
  - TTL-backed storage reduces cleanup burden and matches the temporary nature of the data

**Where it exists in this repo:**

- token revocation:
  - `shared/token_blacklist.py`
- OTP rate limiting and lockout:
  - `services/otp-wrapper/routes.py`
  - `services/otp-wrapper/README.md`
- distributed verification lock:
  - `orchestrators/ticket-verification-orchestrator/routes.py`
  - `orchestrators/ticket-verification-orchestrator/README.md`
- hold cache and idempotency:
  - `services/seat-inventory-service/grpc_server.py`
- purchase-side Redis integration:
  - `orchestrators/ticket-purchase-orchestrator/routes.py`

**What we do not claim:**

- Redis is not the primary business database in this repo
- Redis is not used for long-term records such as tickets, transfers, or credits
- the durable source of truth still lives in the service-owned databases and external systems

**Limitations and tradeoffs:**

- if Redis is unavailable, some convenience and coordination features degrade
- temporary state is only as good as the TTL and key design choices
- Redis adds operational complexity, so it should be reserved for problems that actually benefit from shared fast memory

**Presentation talking points:**

- "The key point is that we use Redis for temporary coordination, not permanent business records."
- "This is beyond the labs because it is not just caching; it includes token revocation, lock ownership, OTP lockouts, and idempotency helpers."
- "The best justification is that these are exactly the kinds of expiring, shared state problems Redis was designed for."

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

**How it works in this repo:**

- clients connect to the notification service over Socket.IO
- clients subscribe to channels such as `seat_update`, `ticket_update`, and `transfer_update`
- internal backend components can call `POST /broadcast`
- the notification service republishes those events through Redis Pub/Sub
- connected clients receive the update immediately without polling

**Why we chose this approach here:**

- ticketing and marketplace-style workflows benefit from immediate frontend updates
- Socket.IO is easier for browser clients than hand-rolled raw WebSocket handling
- Redis Pub/Sub gives the notification layer a shared event bus instead of tying updates to only one process instance
- it cleanly separates "business event happened" from "frontend needs to know now"

**What benefits it gives us compared to other options:**

- compared to frontend polling:
  - clients do not need to keep asking for updates every few seconds
  - updates can appear immediately when state changes
- compared to using only RabbitMQ for notifications:
  - RabbitMQ is aimed at backend job coordination, not direct browser push
  - WebSockets are a better fit for user-facing "something changed right now" feedback
- compared to a single-process WebSocket service with no shared bus:
  - Redis Pub/Sub gives a clearer fan-out mechanism for notification events
  - it is a better foundation for scaling than purely in-memory event routing

**Where it exists in this repo:**

- implementation:
  - `services/notification-service/app.py`
- docs and usage examples:
  - `services/notification-service/README.md`
  - `services/notification-service/NOTIFICATIONS.md`

**Limitations and tradeoffs:**

- realtime connections add more moving parts than plain request-response APIs
- the team has to manage connection lifecycle, subscriptions, and event naming
- WebSockets complement the REST APIs; they do not replace the need for normal HTTP endpoints

**Presentation talking points:**

- "RabbitMQ and WebSockets solve different problems. RabbitMQ is for backend work, while WebSockets are for pushing state changes to the frontend."
- "The beyond-lab part is not just using Socket.IO, but combining it with Redis Pub/Sub so the notification path can fan out events cleanly."
- "This matters for ticketing because seat, ticket, and transfer state changes are time-sensitive from the user's point of view."

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

**How it works in this repo:**

- `shared/queue_setup.py` declares the queue topology for seat-hold expiry, dead-letter routing, seller notifications, and transfer timeout handling
- the purchase flow publishes a hold message to `seat_hold_ttl_queue`
- when that message expires, RabbitMQ dead-letters it into `seat_hold_expired_queue`
- a background consumer then releases the seat via gRPC
- the transfer flow also uses RabbitMQ to notify sellers asynchronously and to auto-cancel stalled transfers after the timeout window

**Why we chose these RabbitMQ patterns here:**

- purchase and transfer flows both have "do something later if the user does nothing" behavior
- RabbitMQ lets the repo treat timeout handling as infrastructure-backed workflow memory instead of relying on a browser staying open
- DLX and TTL queues model expiry explicitly, which is cleaner than scattered timer logic in the app layer
- asynchronous seller notifications keep the live user request shorter and less fragile

**What benefits it gives us compared to other options:**

- compared to basic fire-and-forget queues:
  - TTL queues and dead-letter exchanges let the broker enforce timeout behavior
  - the system can react to expiry rather than hoping application code checks time correctly everywhere
- compared to in-process timers:
  - timers in one process are brittle if that process restarts or scales
  - the broker is a better place to remember delayed workflow actions
- compared to doing everything synchronously:
  - user-facing requests stay shorter
  - background tasks like notifications and timeout cleanup do not block the main interaction path

**Where it exists in this repo:**

- queue topology:
  - `shared/queue_setup.py`
- purchase hold expiry:
  - `orchestrators/ticket-purchase-orchestrator/routes.py`
  - `orchestrators/ticket-purchase-orchestrator/dlx_consumer.py`
  - `orchestrators/ticket-purchase-orchestrator/app.py`
- transfer notifications and timeout:
  - `orchestrators/transfer-orchestrator/routes.py`
  - `orchestrators/transfer-orchestrator/seller_consumer.py`
  - `orchestrators/transfer-orchestrator/timeout_consumer.py`
  - `orchestrators/transfer-orchestrator/app.py`

**Limitations and tradeoffs:**

- advanced queue topology is more complex to explain and debug than simple publish-consume examples
- delayed workflows need careful observability because the action happens later in another consumer
- message-driven recovery logic has to be designed carefully so duplicate or expired messages are handled safely

**Presentation talking points:**

- "The beyond-lab part is not RabbitMQ by itself, but the use of TTL queues, dead-letter routing, and timeout consumers for real workflow control."
- "This matters because seat holds and ticket transfers should still resolve correctly even after the original HTTP request is over."
- "RabbitMQ is acting like workflow memory here, not just a message pipe."

**Read more:**

- [RabbitMQ TTL](https://www.rabbitmq.com/docs/ttl)
- [RabbitMQ Dead Letter Exchanges](https://www.rabbitmq.com/docs/dlx)

---

## BTL #5: Kubernetes Runtime Design

**Simple explanation:**
If Docker containers are like packed lunchboxes, Kubernetes is the school system that decides where every lunchbox goes, restarts it if it falls, and keeps teams separate.

**Why this is beyond the labs:**
The labs covered Docker and Docker Compose. This repo is maintained primarily as a Kubernetes system.

**How it works in this repo:**

- the backend is split into three namespaces: `ticketremaster-edge`, `ticketremaster-core`, and `ticketremaster-data`
- data services such as PostgreSQL, Redis, and RabbitMQ run as Kubernetes-managed data-plane workloads
- orchestrators and services run in the core namespace with readiness and liveness probes
- Kong and Cloudflare-facing edge components run separately in the edge namespace
- Kustomize ties the manifests together into one maintained base deployment

**Why we chose this Kubernetes design:**

- the repo is not just "many containers"; it has distinct edge, core, and data responsibilities
- StatefulSets fit the persistent databases better than stateless deployment patterns
- NetworkPolicies make the runtime layout closer to a real platform than an open flat network
- probes and seed jobs make startup and health behavior part of the deployment design instead of afterthought scripts
- Kustomize gives a single composition point for the stack

**What benefits it gives us compared to other options:**

- compared to Docker Compose only:
  - Kubernetes gives stronger separation of concerns for edge, core, and data
  - it provides probes, StatefulSets, jobs, policies, and declarative rollout behavior that Compose does not model the same way
- compared to a flat cluster with minimal structure:
  - namespaces and network policies make service boundaries more explicit
  - the runtime architecture mirrors the logical architecture of the backend
- compared to treating deployment as a secondary concern:
  - this repo makes deployment topology part of the system design itself
  - health checks, seed jobs, and configuration mounting are first-class design choices

**Where it exists in this repo:**

- entrypoint and composition:
  - `k8s/base/kustomization.yaml`
  - `k8s/base/`
- namespace structure:
  - `k8s/base/namespaces.yaml`
- data plane:
  - `k8s/base/data-plane.yaml`
- core workloads:
  - `k8s/base/core-workloads.yaml`
- edge workloads:
  - `k8s/base/edge-workloads.yaml`
- network isolation:
  - `k8s/base/network-policies.yaml`
- startup data seeding:
  - `k8s/base/seed-jobs.yaml`

**Limitations and tradeoffs:**

- Kubernetes is more complex than Compose, especially for local development and troubleshooting
- the manifest set is larger and requires more operational understanding
- this design adds real structure, but that also means more files and more moving pieces to maintain

**Presentation talking points:**

- "The BTL part is not just that we use containers. It is that we treat the backend as a structured Kubernetes platform with edge, core, and data layers."
- "StatefulSets, NetworkPolicies, readiness probes, and seed jobs show that deployment design here is architectural, not incidental."
- "This is a strong presentation section because it shows system design maturity, not just a different way to start containers."

**Read more:**

- [Kubernetes overview](https://kubernetes.io/docs/concepts/overview/)
- [Namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/)
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)

---

## BTL #6: Cloudflare Tunnel

**Simple explanation:**
Instead of opening the laptop or Minikube cluster directly to the internet, Cloudflare Tunnel lets the cluster make an outbound connection to Cloudflare first. Public users then reach the backend through that tunnel, rather than by connecting straight to the machine running Minikube.

**Why this is beyond the labs:**
Cloudflare Tunnel and zero-trust exposure were not part of the lab stack.

**How it works in this repo:**

- the client hits `https://ticketremasterapi.hong-yi.me`
- Cloudflare routes that request through the configured tunnel
- the `cloudflared` pod in the `ticketremaster-edge` namespace receives the tunnel traffic
- `cloudflared` forwards traffic to Kong inside the cluster
- Kong remains the only browser-facing gateway before requests reach the orchestrators and services

**Why we chose Cloudflare Tunnel here:**

- it gives the project a real public HTTPS URL for demos, frontend integration, and shared smoke testing
- it avoids directly exposing Minikube or the host machine with inbound networking
- it keeps the cluster on an outbound-only connection model, which is a cleaner fit for a laptop-hosted backend
- it fits the repo's existing automation, because the startup flow can bring up the cluster and then verify both the local and public paths
- it preserves the intended edge design where Kong is still the single browser-facing gateway

**What benefits it gives us compared to other options:**

- compared to local-only backend testing:
  - local testing is still supported and is still useful for developer debugging
  - local-only checks prove that `localhost` works, but they do not prove that the shared public URL works
  - the public smoke path helps validate demo access, frontend integration, and the browser-facing route that teammates actually consume
- compared to directly exposing Minikube, opening ports, or using a public IP:
  - Cloudflare Tunnel avoids turning the laptop into a traditionally exposed server
  - it reduces manual networking setup and avoids relying on direct inbound access to the machine
  - it matches the repo's architecture better because Kong stays the controlled ingress point inside Kubernetes
- compared to ad-hoc tunnel tools:
  - this repo is wired around a named public domain, `https://ticketremasterapi.hong-yi.me`, rather than a temporary developer-only address
  - the tunnel is part of the Kubernetes edge deployment, token secret flow, and readiness checks, not a one-off manual step outside the repo

**Why this is useful even though localhost testing already exists:**

- localhost-only testing is enough for isolated developer debugging
- this project also needs to prove that a shared public endpoint works for frontend usage, demos, and team smoke testing
- that is why `start-backend.bat` supports `Localhost only`, `Cloudflare only`, and `Both`, and why `scripts/start_k8s.ps1` can run public smoke checks when the tunnel is configured

**Where it exists in this repo:**

- deployment and runtime:
  - `k8s/base/edge-workloads.yaml` defines the `cloudflared` deployment and the Kong edge service
  - `k8s/base/kustomization.yaml` includes the Cloudflare image pin used by the base stack
- security restrictions:
  - `k8s/base/network-policies.yaml` limits edge traffic so `cloudflared` is the allowed path into Kong and has restricted egress
- secret and token wiring:
  - `scripts/sync_k8s_env.ps1` copies `CLOUDFLARE_TUNNEL_TOKEN` into the `edge-secrets` secret
  - `k8s/base/secrets.local.yaml` is the local secret source that the maintainer fills in
- startup and smoke testing:
  - `start-backend.bat` exposes the startup modes for localhost, Cloudflare, or both
  - `scripts/start_k8s.ps1` waits for `cloudflared`, checks the public gateway, and can run the public smoke flow
- architecture and supporting docs:
  - `README.md` documents Cloudflare Tunnel as part of the edge layer
  - `LOCAL_DEV_SETUP.md` explains the public route and troubleshooting steps
  - `diagrams/12_system_architecture_overview.mmd` shows Cloudflare Tunnel in the system flow

**What we do not claim:**

- this repo clearly uses Cloudflare Tunnel
- this repo does not visibly configure advanced Cloudflare products such as Access policies, WAF rules, or custom DDoS settings
- if asked, those can be described as possible Cloudflare platform capabilities, but not as features currently implemented in this repo

**Limitations and tradeoffs:**

- the repo docs already note that this is still a single-connector public edge, so the public URL can be less stable than a fully hosted production deployment
- Cloudflare Tunnel improves safe exposure, but it does not replace the need for Kong configuration, Kubernetes policies, or application-level security

**Presentation talking points:**

- "We did not choose Cloudflare because localhost testing was impossible. We chose it because localhost only proves the backend works on one machine, while Cloudflare lets us validate the shared public path too."
- "The main architecture benefit is that the cluster stays on an outbound-only model instead of exposing Minikube directly to the internet."
- "In this repo, Cloudflare Tunnel complements Kong. It does not replace Kong. Cloudflare gets traffic safely into the cluster, and Kong remains the actual API gateway."
- "The strongest evidence in the codebase is the `cloudflared` deployment, the edge network policies, and the startup scripts that can check the public URL."

**Read more:**

- [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)

---

## BTL #7: Advanced Kong Usage

**Simple explanation:**
Kong is the front desk of the system. But in this repo it is not just forwarding calls. It is also checking keys, limiting traffic, handling CORS, and keeping route behavior consistent.

**Why this is only partly beyond the labs:**
Kong itself was taught in class. What makes it BTL here is the **deeper production-style usage**, not the fact that Kong exists.

**How it works in this repo:**

- Kong runs in DB-less declarative mode from Kubernetes-managed configuration
- global plugins apply cross-cutting edge behavior such as rate limiting and CORS
- route-level plugins apply `key-auth` only where the route actually needs protection
- the config supports both current no-prefix routes and `/api/...` compatibility routes
- Kong stays the only supported browser-facing gateway into the orchestrators

**Why we chose this Kong design here:**

- it centralizes edge policy instead of duplicating CORS, rate limiting, and gateway concerns in many Flask services
- DB-less declarative config is easier to version with the repo than manual gateway clicks or mutable runtime state
- route-level policy keeps the gateway precise instead of applying one blunt rule to every endpoint
- compatibility routes help the repo support old and new path conventions at the edge layer

**What benefits it gives us compared to other options:**

- compared to pushing all edge behavior into each orchestrator:
  - shared concerns stay in one place
  - route policy is easier to audit and keep consistent
- compared to using Kong only as a simple proxy:
  - this repo uses it as a true API gateway with plugin composition and path policy
  - the gateway is part of the application architecture, not just an HTTP forwarder
- compared to ad-hoc manual gateway setup:
  - the declarative config is versioned in the repo
  - the Kubernetes source of truth matches the deployed environment directly

**Where it exists in this repo:**

- local template and reference:
  - `api-gateway/kong.yml.template`
- Kubernetes source of truth:
  - `k8s/base/configuration.yaml`
- runtime deployment:
  - `k8s/base/edge-workloads.yaml`

**Limitations and tradeoffs:**

- the gateway config is powerful, but it is also another layer developers must understand while debugging
- policy mistakes at the gateway can affect many routes at once
- Kong improves edge consistency, but business authorization still belongs in the services and orchestrators where appropriate

**Presentation talking points:**

- "Kong was taught in class, but here it is used more deeply: DB-less declarative config, global plugins, route-level plugins, and compatibility path handling."
- "The core design idea is that edge policy belongs at the edge, not copied into every Flask service."
- "This is beyond the labs because the repo uses Kong as a managed policy layer, not just as a basic reverse proxy."

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

**How it works in this repo:**

- the purchase confirm flow runs through multiple external and internal steps, including credit checks, seat sale, ticket creation, and credit deduction
- when later steps fail, the purchase flow includes compensating actions such as releasing the seat and marking the ticket appropriately
- the transfer flow uses a multi-step saga across buyer credits, seller credits, transaction logging, ticket ownership change, listing completion, and transfer completion
- the credit top-up flow uses idempotency checks so repeated Stripe confirmations or webhook deliveries do not double-credit the user
- the seat inventory service caches release results so duplicate release requests do not repeat side effects unnecessarily

**Why we chose these patterns here:**

- this backend has workflows that cross multiple services and external systems, so a single database transaction cannot cover the whole path
- ticket purchase and transfer both have real business consequences if the system fails halfway through
- idempotency matters because retries, webhook redelivery, and duplicate requests are normal in distributed systems
- compensation logic is the practical way to keep the system recoverable when atomic all-or-nothing commits are impossible

**What benefits it gives us compared to other options:**

- compared to naive sequential service calls:
  - the repo explicitly handles mid-workflow failure instead of assuming every step will succeed
  - partial success can be cleaned up rather than silently leaving the system inconsistent
- compared to pretending a cross-service workflow is one transaction:
  - this design acknowledges distributed reality
  - it uses compensation and replay protection rather than impossible global atomicity
- compared to having no idempotency guards:
  - duplicate payment events or repeated requests could apply credits or releases multiple times
  - the repo protects several of those replay-prone paths explicitly

**Where it exists in this repo:**

- purchase compensation:
  - `orchestrators/ticket-purchase-orchestrator/routes.py`
- transfer saga:
  - `orchestrators/transfer-orchestrator/routes.py`
- Stripe and top-up idempotency:
  - `orchestrators/credit-orchestrator/routes.py`
- seat release idempotency:
  - `services/seat-inventory-service/grpc_server.py`

**Limitations and tradeoffs:**

- saga logic is harder to reason about than a single local transaction
- compensation is not the same as perfect rollback; it is a recovery strategy
- the team has to think carefully about failure order, duplicate delivery, and what "safe retry" means for each workflow

**Presentation talking points:**

- "This is one of the strongest BTL sections because it shows the backend was designed for failure, not only for happy-path success."
- "The core point is that purchase and transfer are multi-step distributed workflows, so compensation and idempotency are necessary engineering patterns."
- "A good way to explain it is: if a workflow spans services, you cannot rely on one database transaction, so you need recovery logic and replay protection."

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
