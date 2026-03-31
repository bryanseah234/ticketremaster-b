# TicketRemaster Beyond-The-Labs (BTL) Features Report

## Executive Summary

This architectural scan identified **six (6) BTL-qualifying features** in the TicketRemaster codebase. These features demonstrate advanced engineering patterns including gRPC for high-performance communication, Kong API Gateway for edge management, RabbitMQ with advanced messaging patterns, WebSocket real-time notifications with Redis Pub/Sub, external OutSystems integration, and Kubernetes deployment orchestration.

---

## BTL Feature #1: gRPC for High-Performance Seat Inventory

**Identified BTL Feature:** gRPC (Google Remote Procedure Call) with Protocol Buffers

**Code Location:**
- Proto contract: `ticketremaster-b/proto/seat_inventory.proto`
- Generated stubs: `ticketremaster-b/shared/grpc/seat_inventory_pb2.py`, `seat_inventory_pb2_grpc.py`
- Server implementation: `ticketremaster-b/services/seat-inventory-service/`
- Client usage: `ticketremaster-b/orchestrators/ticket-purchase-orchestrator/routes.py` (lines 19-23, 58-120)

**BTL Category:** Advanced Protocols

**Scenario Justification:**
The TicketRemaster platform uses gRPC exclusively for seat inventory operations (`HoldSeat`, `ReleaseSeat`, `SellSeat`, `GetSeatStatus`) to achieve sub-millisecond latency during high-concurrency checkout flows. This is critical because seat reservation requires pessimistic row-level database locks that must execute instantly to prevent double-booking. HTTP REST would introduce unacceptable overhead for these time-sensitive operations. The implementation includes:

- Protocol Buffer contract defining four RPC methods for seat state management
- gRPC channel pooling with configurable pool size (`GRPC_CHANNEL_POOL_SIZE`)
- Host detection and channel lifecycle management
- Integration with the purchase orchestrator's saga pattern for distributed transactions

This demonstrates independent research into high-performance inter-service communication patterns beyond standard REST APIs.

---

## BTL Feature #2: Kong API Gateway

**Identified BTL Feature:** Kong Gateway with declarative configuration

**Code Location:**
- Gateway configuration: `ticketremaster-b/api-gateway/kong.yml`
- Kubernetes deployment: `ticketremaster-b/k8s/base/edge-workloads.yaml`
- Documentation: `ticketremaster-b/README.md` (lines 93-102)

**BTL Category:** API Management

**Scenario Justification:**
Kong serves as the sole public entry point for all browser traffic, providing:

- **Declarative routing** with regex path matching for flexible URL patterns
- **Rate limiting** at both global (50 req/min) and route-specific levels (e.g., 3 req/15min for OTP verification endpoints)
- **Key-based authentication** (`key-auth` plugin) for API access control
- **CORS policy management** for multi-origin frontend support
- **Consumer management** with separate credentials for frontend and partner applications

The gateway isolates internal microservices from direct public access, enforcing security policies at the edge. The configuration demonstrates advanced API management patterns including route-level plugin composition and consumer credential management.

---

## BTL Feature #3: RabbitMQ Advanced Messaging

**Identified BTL Feature:** RabbitMQ with TTL-based delayed messaging and dead-letter exchanges

**Code Location:**
- Queue configuration: `ticketremaster-b/k8s/base/data-plane.yaml`
- Message publishing: `ticketremaster-b/orchestrators/ticket-purchase-orchestrator/routes.py` (lines 200-280)
- Message publishing: `ticketremaster-b/orchestrators/transfer-orchestrator/routes.py` (lines 62-99, 102-158)
- Documentation: `ticketremaster-b/README.md` (lines 133-159)

**BTL Category:** Advanced Messaging

**Scenario Justification:**
The platform implements three sophisticated message queue patterns:

1. **Seat Hold TTL Queue** (`seat_hold_ttl_queue`): Messages have a 5-minute TTL; when a purchase starts, a hold message is published. If the purchase completes, the message is acknowledged and removed. If the TTL expires, the message routes to a dead-letter exchange (`seat_hold_expired_queue`) for automatic seat release.

2. **Seller Notification Queue** (`seller_notification_queue`): Decouples P2P transfer notifications from the buyer's request, enabling asynchronous email/SMS/push delivery with retry logic.

3. **Transfer Timeout Queue** (`transfer_timeout_queue`): Messages with 24-hour TTL for auto-cancelling stuck transfers.

This demonstrates advanced message broker usage including TTL configuration, dead-letter exchanges, and idempotent consumer patterns—far beyond basic queue-based task distribution.

---

## BTL Feature #4: WebSocket Real-Time Notifications with Redis Pub/Sub

**Identified BTL Feature:** Socket.IO WebSocket server with Redis Pub/Sub for cross-service event broadcasting

**Code Location:**
- Service implementation: `ticketremaster-b/services/notification-service/app.py`
- Documentation: `ticketremaster-b/services/notification-service/NOTIFICATIONS.md`
- Frontend integration: `ticketremaster-f/src/composables/useWebSocket.ts`
- Kubernetes deployment: `ticketremaster-b/k8s/base/core-workloads.yaml`

**BTL Category:** Distributed Communication

**Scenario Justification:**
The notification service provides real-time updates to connected clients via WebSocket (Socket.IO), complementing RabbitMQ's async workflows with immediate push notifications. Key features include:

- **Redis Pub/Sub** for cross-service event broadcasting—any service can publish events that are immediately pushed to all connected WebSocket clients
- **Six event types** (`seat_update`, `ticket_update`, `transfer_update`, `purchase_update`, `user_update`, `event_update`) with structured payloads and trace IDs
- **HTTP broadcast API** (`POST /notifications/broadcast`) allowing services to trigger real-time updates without maintaining WebSocket connections
- **Automatic reconnection** and message queuing for resilient client connections

This architecture enables real-time seat availability updates, instant transfer status changes, and live purchase confirmations—critical for a responsive ticketing platform.

---

## BTL Feature #5: OutSystems External Service Integration

**Identified BTL Feature:** Integration with external OutSystems Credit Service as system of record

**Code Location:**
- Integration guide: `ticketremaster-b/OUTSYSTEMS.md`
- Service client: `ticketremaster-b/orchestrators/shared/service_client.py`
- Orchestrator usage: `ticketremaster-b/orchestrators/auth-orchestrator/`, `credit-orchestrator/`, `ticket-purchase-orchestrator/`, `transfer-orchestrator/`

**BTL Category:** External Service Integration

**Scenario Justification:**
The platform integrates with an external OutSystems application as the authoritative system of record for user credit balances. This demonstrates:

- **Cross-platform integration** with API key authentication (`X-API-KEY` header)
- **Saga pattern** for distributed transactions spanning Flask microservices and OutSystems
- **Idempotency handling** via reference IDs for duplicate detection
- **Compensation logic** for rollback on downstream failures
- **Configurable timeout** (`OUTSYSTEMS_TIMEOUT_SECONDS`) for external service calls

The integration follows enterprise patterns for external system communication, including error normalization, retry logic, and circuit breaker patterns.

---

## BTL Feature #6: Kubernetes Multi-Namespace Deployment

**Identified BTL Feature:** Kubernetes deployment with three isolated namespaces (edge, core, data)

**Code Location:**
- Kustomize manifests: `ticketremaster-b/k8s/base/`
- Namespace definitions: `ticketremaster-b/k8s/base/namespaces.yaml`
- Network policies: `ticketremaster-b/k8s/base/network-policies.yaml`
- Core workloads: `ticketremaster-b/k8s/base/core-workloads.yaml`
- Data plane: `ticketremaster-b/k8s/base/data-plane.yaml`

**BTL Category:** Independent Research

**Scenario Justification:**
The platform implements a production-grade Kubernetes deployment architecture with:

- **Three isolated namespaces** (`ticketremaster-edge`, `ticketremaster-core`, `ticketremaster-data`) enforcing architectural layering
- **Network policies** restricting inter-namespace communication to authorized paths only
- **Kustomize** for environment-specific configuration management
- **StatefulSets** for PostgreSQL databases with persistent volume claims
- **ConfigMaps and Secrets** for environment variable management
- **Deployment strategies** with readiness and liveness probes

This demonstrates significant independent research into container orchestration, network security, and production deployment patterns.

---

## BTL Feature #7: Cloudflare Tunnel Zero-Trust Networking

**Identified BTL Feature:** Cloudflare Tunnel (cloudflared) for secure, zero-trust edge exposure

**Code Location:**
- Kubernetes deployment: `ticketremaster-b/k8s/base/edge-workloads.yaml` (lines 87-137)
- Network policies: `ticketremaster-b/k8s/base/network-policies.yaml` (lines 48-104)
- Kustomization: `ticketremaster-b/k8s/base/kustomization.yaml`
- Documentation: `ticketremaster-b/README.md` (line 101)

**BTL Category:** Independent Research

**Scenario Justification:**
The platform uses Cloudflare Tunnel (`cloudflared`) to expose the Kong API Gateway to the internet through a zero-trust architecture. This approach provides:

- **No public IP required** - The cluster remains completely private; `cloudflared` initiates outbound-only connections to Cloudflare's edge
- **Built-in DDoS protection** - All traffic is routed through Cloudflare's global edge network, absorbing volumetric attacks
- **Zero-trust security model** - Eliminates traditional perimeter security in favor of identity-aware access controls
- **Global edge performance** - API requests are routed to the nearest Cloudflare edge location, reducing latency
- **Simplified infrastructure** - No need for load balancers, firewall rules, or VPN infrastructure

The deployment includes:
- **High availability** with 2 replicas
- **Metrics exposure** on port 2000 for monitoring
- **Restricted network policies** limiting `cloudflared` to only necessary communication paths
- **Secret-based authentication** using Cloudflare tunnel tokens

This demonstrates independent research into modern zero-trust networking patterns and edge computing architectures.

---

## Summary Table

| BTL Feature | Category | Primary Location | Complexity Level |
|-------------|----------|------------------|------------------|
| gRPC Seat Inventory | Advanced Protocols | `proto/`, `shared/grpc/` | High |
| Kong API Gateway | API Management | `api-gateway/kong.yml` | High |
| RabbitMQ Advanced Messaging | Advanced Messaging | `orchestrators/*/routes.py` | High |
| WebSocket + Redis Pub/Sub | Distributed Communication | `services/notification-service/` | High |
| OutSystems Integration | External Service Integration | `OUTSYSTEMS.md` | Medium |
| Kubernetes Multi-Namespace | Independent Research | `k8s/base/` | High |
| Cloudflare Tunnel Zero-Trust | Independent Research | `k8s/base/edge-workloads.yaml` | High |

---

*Report generated from architectural scan of TicketRemaster codebase. All code locations verified against current repository state.*
