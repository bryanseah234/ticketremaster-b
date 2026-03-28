# TicketRemaster Kubernetes Architecture Specification

## 1. Objective

This document defines the target Kubernetes architecture for TicketRemaster as it moves from Docker Compose to a production-style cluster model. The design covers:

- Kong as the internal API Gateway and Kubernetes ingress control plane
- Cloudflare Tunnel as the external exposure mechanism for the public API
- Redis as a low-latency cache for seat hold verification with gRPC and database fallback
- Ordered, idempotent database seeding using Kubernetes-native primitives
- Centralized CORS, client identity propagation, and layered rate limiting

This specification intentionally does not include manifests, scripts, or implementation code.

## 2. Confirmed Design Inputs

- Frontend domain: `https://ticketremaster.hong-yi.me`
- Public API domain: `https://ticketremasterapi.hong-yi.me`
- External API traffic enters through Cloudflare Tunnel and terminates at Kong
- Kong remains private inside the cluster and is not exposed through a public load balancer
- Rate limiting is layered across Cloudflare and Kong
- Seed data runs as a bootstrap-once, ordered, idempotent workflow
- Redis caching must preserve the existing source-of-truth model in which Redis accelerates reads but gRPC and PostgreSQL remain authoritative
- The immediate deployment target is a local Kubernetes environment such as Docker Desktop, used as a production-equivalent validation environment before migration to GCP

## 3. Current System Constraints Incorporated

The design aligns to the current backend behavior described in the repository:

- Kong is already the single API entry point for frontend traffic
- Orchestrators remain the only browser-facing backend layer
- `ticket-purchase-orchestrator` uses gRPC with `seat-inventory-service` for hold, release, sale, and seat status checks
- RabbitMQ continues to handle seat-hold expiry and asynchronous workflows
- Seeding currently follows the strict order `venues -> events -> seats -> inventory`
- Existing Kong CORS behavior already recognizes the frontend and API domains and should be migrated into the Kubernetes gateway policy model

## 4. Target Topology

### 4.1 Control and Runtime Planes

- **Namespace model**
  - `ticketremaster-core` for application services and orchestrators
  - `ticketremaster-edge` for Kong and cloudflared
  - `ticketremaster-data` for PostgreSQL databases, Redis, and RabbitMQ

- **Edge exposure**
  - Cloudflare manages DNS and public TLS for `ticketremasterapi.hong-yi.me`
  - A `cloudflared` Deployment establishes outbound-only tunnel connectivity from the cluster to Cloudflare
  - `cloudflared` forwards incoming API traffic to the internal Kong proxy Service
  - Kong routes requests to orchestrator Services inside the cluster

- **Application plane**
  - Orchestrators run as stateless Deployments
  - Atomic services run as separate Deployments
  - Each service continues to own its own PostgreSQL database
  - `seat-inventory-service` continues to expose both HTTP and gRPC internally

- **Data plane**
  - PostgreSQL runs as StatefulSets or managed databases
  - Redis runs as a dedicated StatefulSet or managed Redis offering
  - RabbitMQ runs as a StatefulSet or managed broker

### 4.2 Exposure Boundaries

- **Publicly reachable**
  - `ticketremasterapi.hong-yi.me` through Cloudflare only

- **Private cluster-only**
  - Kong Admin API
  - Kong proxy Service
  - All orchestrator Services
  - All atomic service Services
  - Redis
  - RabbitMQ
  - PostgreSQL Services
  - gRPC endpoints

This preserves the existing architectural principle that frontend traffic reaches orchestrators only through the gateway layer.

### 4.3 Local Kubernetes Reliability Constraints

- The local Docker Desktop Kubernetes environment is a topology-validation and resilience-test environment, not a throughput-accurate scale benchmark
- Local testing must assume constrained CPU, memory, disk I/O, and DNS responsiveness compared to GCP
- Priority for local cluster stability should be given to Kong, `cloudflared`, Redis, RabbitMQ, `ticket-purchase-orchestrator`, and `seat-inventory-service`
- Local validation should prefer correctness, dependency readiness, and failure-mode testing over high-concurrency benchmarking
- Multi-replica testing in local Kubernetes should be deliberate and selective because indiscriminate replication can produce false negatives caused by workstation limits rather than architecture flaws

## 5. End-to-End Request Flow

### 5.1 Public API Flow

1. The frontend at `ticketremaster.hong-yi.me` sends HTTPS requests to `ticketremasterapi.hong-yi.me`
2. Cloudflare receives the request, applies edge protections, and forwards it through the named tunnel
3. A `cloudflared` pod inside Kubernetes receives the tunneled request
4. `cloudflared` forwards the request to the internal Kong proxy Service
5. Kong applies CORS, authentication, route policies, and API-aware rate limiting
6. Kong forwards the request to the correct orchestrator Service
7. The orchestrator performs internal REST or gRPC calls to atomic services
8. The response returns through Kong, back through the tunnel, and then to the frontend

### 5.2 Seat Purchase Hold and Confirm Flow

1. Frontend calls `POST /purchase/hold/:inventoryId` through the public API hostname
2. Kong routes to `ticket-purchase-orchestrator`
3. The orchestrator calls `seat-inventory-service` over gRPC to acquire the hold with pessimistic locking
4. `seat-inventory-service` commits the hold in PostgreSQL
5. After successful commit, the service writes the corresponding `hold:{inventoryId}` record into Redis with TTL matching the hold duration
6. A later `POST /purchase/confirm/:inventoryId` request first validates the hold from Redis
7. On Redis hit, the purchase flow avoids an extra gRPC status check
8. On Redis miss or Redis failure, the orchestrator falls back to the existing gRPC `GetSeatStatus` path
9. After successful sale or release, the Redis hold key is removed

This maintains the current correctness model: Redis improves latency, but it never becomes the system of record.

## 6. Kong Architecture

### 6.1 Kong Role

Kong remains the single HTTP gateway for all browser-originated backend traffic. It should continue routing only to orchestrators for public APIs, not directly to atomic services.

### 6.2 Kong Deployment Model

- Run Kong as an internal Deployment in the edge namespace
- Expose the Kong proxy through an internal ClusterIP Service
- Keep the Kong Admin API private and reachable only by operators or CI/CD automation within the cluster
- Avoid public LoadBalancer Services because Cloudflare Tunnel becomes the sole external entry path

### 6.3 Route Ownership

Kong should own route policy for the frontend contract, including:

- `/auth`
- `/credits`
- `/events`
- `/purchase`
- `/marketplace`
- `/transfer`
- `/tickets`
- `/verify`

This mirrors the frontend-facing orchestration contract and keeps atomic service routes internal.

## 7. Cloudflare Tunnel Integration

### 7.1 Recommended Network Pattern

- Deploy `cloudflared` inside Kubernetes as a highly available Deployment
- Use outbound tunnel connectivity so no public IP or external load balancer is required for Kong
- Configure the public hostname `ticketremasterapi.hong-yi.me` to forward to the internal Kong proxy Service
- Keep tunnel scope limited to the API hostname; the frontend remains independently hosted at `ticketremaster.hong-yi.me`

### 7.2 What to Put in the Cloudflare Dashboard

For the Cloudflare Tunnel public hostname that serves `ticketremasterapi.hong-yi.me`, the origin URL should point to the **internal Kong Service DNS name and Service port**, not the pod IP and not the container port unless the Service also exposes that port.

- **For local Docker Compose**
  - Place `cloudflared` on the same Docker network as Kong
  - If `cloudflared` runs as a container on that same Docker network, use `http://kong:8000`
  - If `cloudflared` runs outside the Docker network, use the address reachable from where `cloudflared` runs, typically `http://localhost:8000` or the host-reachable equivalent

- **For Kubernetes**
  - Use the Kong proxy Service DNS name in the namespace where Kong is deployed
  - Recommended form: `http://<kong-proxy-service>.<namespace>.svc.cluster.local:<service-port>`
  - Selected origin URL for this architecture: `http://kong-proxy.ticketremaster-edge.svc.cluster.local:80`

The local Kubernetes testbed and the future GCP deployment should both preserve this same pattern: Cloudflare Tunnel points to the **internal Kong Service DNS plus Service port**, not to pod IPs and not to a public load balancer.

### 7.3 Tunnel Availability

- Run more than one `cloudflared` replica so tunnel availability is not tied to a single pod
- Keep tunnel credentials in Kubernetes Secrets
- Restrict egress from the cloudflared pods to only required destinations
- Ensure the cloudflared Deployment can resolve and reach the Kong proxy Service
- Treat forwarded client identity as trusted only when requests arrive through the approved Cloudflare Tunnel path
- Do not allow arbitrary internal workloads to inject or override forwarded client identity headers that Kong will later trust

## 8. CORS Strategy

### 8.1 Policy Location

CORS should be enforced centrally at Kong rather than independently inside every orchestrator. This keeps browser behavior consistent and simplifies service ownership.

### 8.2 Allowed Origins

The allowed browser origins should include:

- `https://ticketremaster.hong-yi.me`
- approved preview or staging frontend domains if you choose to support them
- local development origins only in non-production environments

### 8.3 Origin Policy Hardening

- Production should use an explicit allowlist that includes `https://ticketremaster.hong-yi.me` and nothing broader by default
- Preview or staging origins should be enabled only through a separate non-production allowlist and should not be implied by production policy
- Wildcard origin behavior should remain disallowed for credentialed browser traffic
- Browser-facing CORS acceptance should be treated as a release gate and tested before frontend cutover

### 8.4 Policy Expectations

- Allow credentials only if frontend authentication requires cookies or credentialed cross-origin requests
- Allow headers required by the current frontend and gateway contract, including `Authorization`, `Content-Type`, request correlation headers, and any gateway-managed client credentials headers
- Support `OPTIONS` preflight handling at Kong
- Do not use wildcard origins in production because the frontend origin is already well-defined

### 8.5 Browser Path

The frontend should call only `https://ticketremasterapi.hong-yi.me`, never individual service hostnames. This keeps cross-origin behavior predictable and aligns with the existing orchestrator-only rule.

## 9. Client IP Preservation and Rate Limiting

### 9.1 Desired Behavior

Kong rate-limiting plugins must identify the actual client, not the `cloudflared` pod or an internal Service IP.

### 9.2 Trust Model

Because Kong is private and only reachable from inside the cluster, it should trust forwarded client identity only from the `cloudflared` origin path, not from arbitrary application pods.

### 9.3 Identity Safety Requirement

- Real client IP extraction must be treated as a mandatory edge-control requirement, not a best-effort enhancement
- If Kong cannot confidently resolve trusted forwarded client identity, rate limiting should fall back to a conservative bucket and raise an operational signal
- Release validation must prove that Kong rate limits against the caller identity rather than the tunnel pod identity

### 9.4 Practical Design

- Cloudflare edge receives the true client IP
- Cloudflare forwards the request through the tunnel with the appropriate forwarding headers
- `cloudflared` passes those headers to Kong
- Kong is configured to treat Cloudflare-provided forwarded client identity as authoritative for proxied requests arriving from the tunnel path
- Kong rate-limiting plugins key on the real client address or authenticated consumer identity instead of the immediate source IP of the tunnel pod

### 9.5 Layered Rate-Limit Model

- **Cloudflare layer**
  - coarse bot protection
  - volumetric abuse controls
  - edge request filtering
  - optional WAF rules for obviously malicious patterns

- **Kong layer**
  - route-aware and consumer-aware limits
  - stricter limits on sensitive endpoints such as login, registration, purchase confirmation, OTP, and transfer verification
  - differentiated policy by anonymous versus authenticated traffic

### 9.6 Recommended Identity Hierarchy for Limits

Use the following order of preference for policy identity:

1. authenticated consumer or JWT subject for protected routes
2. forwarded real client IP for anonymous routes
3. a conservative fallback bucket if forwarded identity is unavailable

This keeps authentication-heavy flows resilient even when multiple users sit behind the same network.

## 10. Redis Caching Architecture

### 10.1 Scope

Redis is introduced as a read-aside cache specifically for seat hold validation during purchase confirmation. It is not a replacement for gRPC and not a replacement for PostgreSQL.

### 10.2 Placement

- Deploy Redis in the data namespace
- Expose it by ClusterIP Service only
- Provide a stable DNS name through a StatefulSet-backed Service or a managed Redis endpoint
- Store Redis connection details in Kubernetes configuration and secrets as appropriate

### 10.3 Runtime Behavior

- `seat-inventory-service` writes the hold record to Redis only after the database transaction commits successfully
- `seat-inventory-service` deletes the hold key when a hold is released or sold
- `ticket-purchase-orchestrator` checks Redis first during purchase confirmation
- If Redis misses or is unavailable, the orchestrator falls back to gRPC `GetSeatStatus`
- PostgreSQL remains the authoritative source of truth

### 10.4 Operational Requirements

- TTL on Redis keys must match seat hold expiry duration
- Redis outages must degrade gracefully to the existing gRPC path
- Redis should not be used for permanent inventory state
- Observability should include cache hit rate, miss rate, failure count, and hold-key TTL behavior

### 10.5 Failure-Mode Hardening

- The accepted cache inconsistency mode should be cache omission, not cache authority drift
- If the database commit succeeds and the Redis write fails, the system must remain correct by falling back to gRPC and PostgreSQL, even if latency increases
- Redis misses during purchase confirmation should be monitored as a protected-path event because sustained misses can create fallback pressure on gRPC and PostgreSQL
- High-concurrency Redis misses should be treated as a potential fallback storm and guarded operationally with conservative limits and alerting

### 10.6 Kubernetes Workload Recommendation

- Use a Redis StatefulSet if running in-cluster
- Start with a single primary for simplicity unless high availability is a hard requirement
- Apply a persistent volume only if you want restart resilience for cached keys, though the design remains functionally correct even when the cache is empty after restart

## 11. Database and Messaging Workloads

### 11.1 PostgreSQL

- Each domain database remains isolated
- Prefer managed PostgreSQL where possible because the platform already operates many separate databases
- If self-hosted in-cluster, use StatefulSets with durable persistent volumes and backup policy per database

### 11.2 RabbitMQ

- RabbitMQ remains required for seat hold expiry and seller-notification flows
- Keep it private inside the cluster
- Maintain the existing exchange and queue semantics
- Ensure orchestrators and services reference RabbitMQ through internal Service DNS

## 12. Automated Seeding Strategy

### 12.1 Goal

Replace the current manual Docker copy-and-exec flow with a Kubernetes-native bootstrap process that is ordered, idempotent, and safe to re-run for a new environment.

### 12.2 Required Sequence

The sequence remains:

1. venues
2. events
3. seats
4. seat inventory

This order is non-negotiable because later datasets depend on earlier entities already existing.

### 12.3 Recommended Kubernetes Pattern

Use a **bootstrap-once seeding workflow** built from Jobs rather than embedding seeds inside long-running app pods.

Recommended model:

- one Job per seed stage
- each Job waits for the required database and upstream service dependencies to be healthy
- each Job runs the existing idempotent Python seed logic for its domain
- each Job completes and exits successfully before the next Job starts
- the workflow is invoked only for fresh environment bootstrap, not on every rollout
- each stage should publish a clear completion outcome so later stages do not infer success from pod startup alone

### 12.4 Why Jobs Instead of Init Containers

Init containers are useful inside a single pod startup path, but they are a weaker fit here because:

- seeding spans multiple independent services and databases
- the process must enforce cross-service ordering
- bootstrap should be decoupled from routine application restarts
- re-running a web pod should not risk re-triggering the whole seed chain

### 12.5 Orchestration Model

The seeding chain should be represented as:

- `seed-venues`
- `seed-events`
- `seed-seats`
- `seed-seat-inventory`

Each stage should start only after:

- its own database is ready
- any service API dependencies are reachable
- the previous seed stage has completed successfully

### 12.6 Idempotency Expectations

The existing seed scripts already describe re-run safety. Preserve that behavior in Kubernetes by ensuring:

- seeds check for existing records before insert
- failures can be retried without creating duplicates
- bootstrap can be safely re-applied in a new cluster or wiped environment

### 12.7 Bootstrap Safety Controls

- Seed progression should depend on verified dependency usability, not merely container start or pod readiness
- A partially completed bootstrap must be detectable so operators can distinguish never-started, in-progress, failed, and completed seed states
- Later seed stages must not begin when an earlier stage exits ambiguously or leaves the environment in a partially populated state
- Seed retries should be bounded and observable so repeated failures do not silently loop during cluster bring-up

### 12.8 Recommended Operational Trigger

- Automatically run the seed workflow only for new lower environments or first-time environment creation
- In production, keep seed execution as a controlled bootstrap step within the release pipeline rather than attaching it to every deployment

## 13. Service Discovery and Configuration Model

### 13.1 Internal Discovery

All service-to-service communication should move from Docker hostnames to Kubernetes Service DNS names.

- HTTP service URLs point to internal ClusterIP Services
- gRPC host and port point to the `seat-inventory-service` internal Service
- Redis, RabbitMQ, and databases are resolved through internal Services or managed endpoints

### 13.2 Configuration Separation

- Non-secret runtime configuration belongs in ConfigMaps or an equivalent external configuration source
- Secrets such as JWT, Stripe, OutSystems, SMU, QR, database credentials, Redis credentials if enabled, RabbitMQ credentials, and Cloudflare tunnel credentials belong in Kubernetes Secrets or an external secret manager

### 13.3 Security Note

The current repository `.env` contains sensitive values and a tunnel token. Those values should not be copied directly into plain-text Kubernetes manifests. They should be rotated if already exposed and reintroduced through secret management.

## 14. Security Architecture

### 14.1 External Security Boundary

- Cloudflare provides public TLS termination and edge filtering
- Only the Cloudflare Tunnel exposes the API hostname externally
- Kong and all backend Services remain private

### 14.2 Internal Security Controls

- Apply NetworkPolicies so only approved namespaces and workloads can reach Kong, Redis, RabbitMQ, and databases
- Limit Kong Admin API access to operators or automation only
- Keep gRPC traffic internal to the cluster
- Keep direct access from the frontend to atomic services impossible by DNS and network design

### 14.3 Authentication

- Preserve JWT-based authentication at the orchestrator layer
- Let Kong enforce route policy, CORS, and rate limits without taking ownership of application business authorization decisions

## 15. Availability and Scaling

### 15.1 Stateless Components

Scale these horizontally:

- orchestrators
- atomic HTTP services
- Kong
- cloudflared

### 15.2 Stateful Components

Scale and harden separately:

- PostgreSQL
- Redis
- RabbitMQ

### 15.3 Purchase Path Priorities

Give higher operational priority to:

- Kong
- `ticket-purchase-orchestrator`
- `seat-inventory-service`
- Redis
- RabbitMQ

These components directly influence the checkout experience and hold lifecycle.

### 15.4 Local Resource Guardrails

- Local Kubernetes should reserve enough capacity for edge and purchase-path components before enabling optional workloads
- When workstation resources are constrained, non-critical services should be deprioritized before Kong, Redis, RabbitMQ, and the purchase path are impacted
- Local load testing should be capped to levels that do not invalidate results through host-level saturation
- Operational findings from local Kubernetes should be classified as topology-valid unless reproduced under a more production-like resource envelope

## 16. Observability Requirements

### 16.1 Metrics

Track at minimum:

- request rate and latency at Cloudflare and Kong
- per-route 4xx and 5xx counts
- Redis cache hit and miss rates for seat hold lookups
- gRPC call latency between `ticket-purchase-orchestrator` and `seat-inventory-service`
- RabbitMQ queue depth and DLX activity
- Job completion status for seed stages

### 16.2 Logging

- Propagate a correlation or trace ID from Kong through orchestrators and services
- Record whether purchase confirmation used Redis hit, Redis miss, or gRPC fallback
- Log seed workflow success and failure by stage

### 16.3 Alerts

Alert on:

- tunnel disconnected
- Kong route failures
- Redis unavailable or sustained low hit ratio
- abnormal growth in purchase confirmation errors
- seeding job failure during environment bootstrap

## 17. Rollout Strategy

### 17.1 Migration Order

1. establish namespaces, secrets, and internal Services
2. deploy data plane components
3. deploy atomic services and orchestrators
4. deploy Kong privately
5. deploy cloudflared and map `ticketremasterapi.hong-yi.me`
6. validate CORS and client IP propagation
7. introduce Redis-backed hold caching
8. execute bootstrap seed workflow for fresh environments
9. enable autoscaling and hardening policies

### 17.2 Validation Gates

Before production cutover, validate:

- frontend requests from `ticketremaster.hong-yi.me` succeed through `ticketremasterapi.hong-yi.me`
- preflight CORS behavior is correct for browser requests
- Kong logs and rate-limiting behavior see real client identity, not tunnel pod identity
- purchase confirm succeeds on Redis hit and on forced Redis fallback
- the seed chain completes in the correct order without duplicates
- local resource pressure does not cause false architectural failures in Kong, Redis, RabbitMQ, or the purchase path
- seed stages report unambiguous completion state across success, retry, and failure cases

## 18. Phased Implementation Plan

### Phase 1. Local Kubernetes Foundation

- Stand up a local Kubernetes cluster in Docker Desktop as the immediate production-equivalent testbed
- Create the target namespace layout for edge, core, and data workloads
- Move current `.env` concerns into a Kubernetes-oriented configuration model that separates secrets from non-secret runtime settings
- Define internal Service naming conventions that mirror the cluster DNS model to be reused later in GCP

### Phase 2. Data Plane Migration

- Deploy PostgreSQL, RabbitMQ, and Redis into the local Kubernetes cluster
- Preserve database-per-service isolation instead of collapsing data stores
- Validate internal connectivity from services to databases, RabbitMQ, and Redis using cluster DNS names
- Establish baseline persistence, restart behavior, and operational recovery expectations in the local environment

### Phase 3. Application Plane Migration

- Deploy atomic services first so orchestrators can bind to stable internal endpoints
- Deploy orchestrators as stateless workloads with all browser-facing traffic still intended to enter through Kong only
- Preserve the internal gRPC path between `ticket-purchase-orchestrator` and `seat-inventory-service`
- Validate the existing RabbitMQ-based hold expiry and asynchronous flows in Kubernetes before introducing public traffic

### Phase 4. Kong Internalization

- Deploy Kong privately inside the `ticketremaster-edge` namespace
- Expose Kong through an internal ClusterIP proxy Service named and ported to support the selected tunnel origin target
- Recreate the existing frontend-facing route ownership for orchestrator paths only
- Re-establish centralized CORS policy in Kong for `https://ticketremaster.hong-yi.me` and any explicitly approved non-production frontend origins

### Phase 5. Cloudflare Tunnel Attachment

- Deploy `cloudflared` in Kubernetes and bind the tunnel to `ticketremasterapi.hong-yi.me`
- Configure the Cloudflare dashboard origin URL as `http://kong-proxy.ticketremaster-edge.svc.cluster.local:80`
- Validate that Kong stays private while the API becomes reachable only through the tunnel
- Confirm that Cloudflare-provided forwarded client identity reaches Kong correctly for downstream logging and rate limiting

### Phase 6. Policy Hardening

- Apply layered rate limiting with coarse controls at Cloudflare and route-aware controls at Kong
- Lock down Kong Admin API access and add namespace-level network restrictions
- Verify that CORS preflight, browser credentials behavior, and protected route access work from the frontend domain
- Confirm that rate limiting keys off the real client identity rather than the `cloudflared` pod identity

### Phase 7. Redis Cache Activation

- Introduce Redis-backed seat hold caching without changing the source-of-truth model
- Validate write-after-commit behavior in `seat-inventory-service`
- Validate read-first behavior in `ticket-purchase-orchestrator` with successful gRPC fallback on cache miss or outage
- Measure cache hit ratio and purchase confirmation latency changes in the local Kubernetes environment

### Phase 8. Bootstrap Seeding Automation

- Replace manual copy-and-exec seed steps with ordered Kubernetes Jobs
- Enforce the sequence `venues -> events -> seats -> inventory`
- Ensure each stage is idempotent and can be retried safely for new environments
- Keep the workflow bootstrap-only rather than tying it to every application rollout

### Phase 9. Production-Equivalent Validation

- Run end-to-end frontend and API validation against the local Kubernetes environment
- Test failure scenarios including Redis outage, tunnel interruption, and seeded environment rebuild
- Verify observability coverage across Kong, `cloudflared`, Redis, RabbitMQ, orchestrators, and seed Jobs
- Use this local environment as the acceptance gate before promoting the same architecture shape to GCP

### Phase 10. GCP Transition

- Preserve the same logical architecture when moving from Docker Desktop Kubernetes to GCP
- Keep Cloudflare Tunnel terminating into private Kong connectivity rather than introducing a public ingress endpoint unless explicitly required later
- Swap local stateful implementations for managed services where appropriate without changing service boundaries or traffic flow
- Re-run the same validation gates used in local Kubernetes before opening production traffic

## 19. Final Recommended Decisions

- Use Cloudflare Tunnel as the only public entry path for the API hostname
- Keep Kong private and internal to the cluster
- Route public browser traffic only to orchestrators via Kong
- Centralize CORS and route policy in Kong
- Preserve real client identity through the tunnel so Kong rate limits on the caller, not the tunnel pod
- Use Redis only as a hold-status acceleration layer with gRPC and PostgreSQL fallback
- Automate seed bootstrap using ordered, idempotent Kubernetes Jobs
- Keep all secrets out of plain-text manifests and move them into a managed secret workflow

## 20. Appendix A: Environment Variable Mapping Strategy

### 20.1 Secrets

These values should move into Kubernetes Secrets or an external secret manager and should not live in plain ConfigMaps:

- `JWT_SECRET`
- `QR_SECRET`
- `QR_ENCRYPTION_KEY`
- `OUTSYSTEMS_API_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `SMU_API_KEY`
- `RABBITMQ_USER`
- `RABBITMQ_PASS`
- all `*_DB_PASSWORD` values
- all database connection strings containing credentials, if full URLs are preserved
- `CLOUDFLARE_TUNNEL_TOKEN`

### 20.2 Non-Secret Runtime Configuration

These values belong in ConfigMaps or an equivalent non-secret configuration layer:

- `APP_ENV`
- `LOG_LEVEL`
- `PYTHONUNBUFFERED`
- `QR_TTL_SECONDS`
- `SEAT_HOLD_DURATION_SECONDS`
- `SMU_API_URL`
- `CREDIT_SERVICE_URL`
- `RABBITMQ_HOST`
- `RABBITMQ_PORT`
- `RABBITMQ_MANAGEMENT_PORT`
- `SEAT_INVENTORY_GRPC_HOST`
- `SEAT_INVENTORY_GRPC_PORT`
- all internal `*_SERVICE_URL` values
- all database host, port, name, and username values that do not contain secrets

### 20.3 Recommended Configuration Pattern

- Keep application-level knobs and hostnames in ConfigMaps
- Keep sensitive values in Secrets
- Prefer composing database URLs inside the application entrypoint or workload environment from secret and non-secret fragments instead of storing large credential-bearing URLs everywhere
- Keep local Kubernetes and GCP naming aligned so service discovery changes as little as possible between environments

### 20.4 Environment-Specific Notes

- In local Kubernetes, internal service URLs should resolve to ClusterIP Services rather than Docker hostnames
- In GCP, preserve the same variable names even if the backing endpoints move to managed services
- For Cloudflare Tunnel, inject the tunnel token only into the `cloudflared` workload and not into unrelated application pods
- For Redis, add a dedicated `REDIS_URL` or equivalent runtime setting only to the workloads that participate in hold caching

## 21. Appendix B: Kong Route Ownership by Orchestrator

### 21.1 Public Browser-Facing Route Map

Kong should own only the frontend-facing route surface and forward each path group to the correct orchestrator:

- `/auth/*` -> `auth-orchestrator`
- `/credits/*` -> `credit-orchestrator`
- `/events` and `/events/*` -> `event-orchestrator`
- `/purchase/*` -> `ticket-purchase-orchestrator`
- `/marketplace/*` -> `marketplace-orchestrator`
- `/transfer/*` -> `transfer-orchestrator`
- `/tickets` and `/tickets/*` -> `qr-orchestrator` for end-user ticket and QR retrieval flows
- `/verify/*` -> `ticket-verification-orchestrator` for staff validation flows

### 21.2 Route Ownership Principles

- Kong should not expose atomic service routes publicly
- Kong should route only to orchestrators for browser-originated traffic
- Atomic services remain reachable only over internal cluster networking
- Route ownership should reflect the frontend contract rather than the internal service topology

### 21.3 Policy Priorities by Route Group

- **High sensitivity**
  - `/auth/*`
  - `/purchase/*`
  - `/transfer/*`
  - `/verify/*`

- **Moderate sensitivity**
  - `/credits/*`
  - `/marketplace/*`
  - `/tickets/*`

- **Public read-heavy**
  - `/events`
  - `/events/*`

### 21.4 Recommended Kong Enforcement Split

- Apply global CORS and baseline protections once at the gateway
- Apply stricter route-specific rate limits for authentication, purchase, transfer, OTP, and verification traffic
- Keep application authorization decisions inside orchestrators even when Kong performs gateway-level authentication checks
- Preserve correlation IDs across all routed traffic for observability and debugging

## 22. Appendix C: Seed Dependency Matrix

### 22.1 Ordered Bootstrap Chain

The bootstrap workflow should remain:

1. `seed-venues`
2. `seed-events`
3. `seed-seats`
4. `seed-seat-inventory`

### 22.2 Dependency Table

| Seed Stage | Primary Data Written | Must Wait For | Depends On Prior Seed Data | Why Ordering Matters |
|---|---|---|---|---|
| `seed-venues` | venue records | venue database and venue service readiness | none | venues are the root reference for downstream entities |
| `seed-events` | event records | event database and event service readiness | venues | events must attach to valid venues |
| `seed-seats` | seat records | seat database and seat service readiness | venues | seats must attach to valid venues and seating layouts |
| `seed-seat-inventory` | inventory records | seat inventory database and seat inventory service readiness | events and seats | inventory must bind existing events to existing seats |

### 22.3 Execution Rules

- Each seed Job should start only after its required database endpoint is healthy
- Each seed Job should also verify that any required upstream service API is reachable if the existing script depends on service-layer behavior
- A later seed stage must never begin before the prior stage has completed successfully
- Failed stages should be retryable without creating duplicate records

### 22.4 Operational Guidance

- Run the full chain for new local Kubernetes environments and other fresh bootstrap scenarios
- Keep production seeding controlled and explicit rather than attached to every application deployment
- Treat seed completion as an environment bootstrap milestone and surface it in operational dashboards
- If future datasets are added, extend the chain by dependency order rather than bundling all seed logic into one monolithic job

## 23. Appendix D: Audit Hardening Controls

### 23.1 Local Kubernetes Controls

- Treat Docker Desktop Kubernetes as a constrained reliability environment rather than a direct performance proxy for GCP
- Protect the edge and purchase path first when local resources are limited
- Use local failures to validate dependency handling, not to extrapolate production throughput

### 23.2 Edge Identity and CORS Controls

- Trust forwarded client identity only from the Cloudflare Tunnel path
- Require explicit production origin allowlisting for `https://ticketremaster.hong-yi.me`
- Keep preview-origin access separate from production-origin policy
- Fail release validation if Kong rate limiting resolves the tunnel pod identity instead of the caller identity

### 23.3 Bootstrap and Cache Controls

- Treat seeding as an environment-state transition with explicit completion semantics
- Block downstream seed stages until upstream stage success is unambiguous
- Accept Redis omission as survivable but monitor fallback storms aggressively
- Alert on sustained Redis misses or abnormal purchase-path fallback rates

## 24. Single-Sentence Architecture Summary

TicketRemaster on Kubernetes should use Cloudflare Tunnel to privately expose `ticketremasterapi.hong-yi.me` to an internal Kong gateway, route frontend traffic only to orchestrators, preserve Redis as a non-authoritative read-aside cache for seat holds with gRPC fallback, and replace manual seed execution with a one-time ordered Job-based bootstrap workflow.
