# TicketRemaster Backend

TicketRemaster is a Kubernetes-first backend for event discovery, seat inventory, credit top-ups, ticket purchase, QR retrieval, staff verification, resale marketplace, and peer-to-peer ticket transfer.

The repository currently contains:

- 8 Flask orchestrators for browser-facing workflows
- 13 internal services and wrappers
- 1 Socket.IO notification service
- 10 PostgreSQL databases, each owned by a single service
- Redis for short-lived workflow state and locking support
- RabbitMQ for delayed and asynchronous workflow processing
- Kong 3.9 as the only browser-facing gateway
- Cloudflare Tunnel for optional public exposure of the local cluster
- committed Kubernetes manifests under `k8s/base`

## Current stack

- Runtime: Python 3.12 on `python:3.12-slim`
- Web framework: Flask + Flasgger
- Persistence: PostgreSQL + Flask-SQLAlchemy + Flask-Migrate
- Gateway: Kong 3.9 in DB-less declarative mode
- Messaging: RabbitMQ 3 management image
- Cache and locks: Redis 7
- Internal RPC: gRPC for seat hold and sale operations
- Payments: Stripe wrapper service
- External system of record: OutSystems credit API
- OTP integration: OutSystems notification API wrapper
- Realtime: Flask-SocketIO + Redis Pub/Sub

## Architecture

TicketRemaster is deliberately split into layers that match the committed Kubernetes namespaces.

| Layer | Namespace | Owns |
| --- | --- | --- |
| Edge | `ticketremaster-edge` | Kong, cloudflared, gateway policy |
| Core | `ticketremaster-core` | Orchestrators, services, wrappers, seed jobs |
| Data | `ticketremaster-data` | PostgreSQL StatefulSets, Redis, RabbitMQ |

### Design logic

- Orchestrators own browser-facing workflow composition and access control.
- Atomic services own a single bounded context and, where applicable, a dedicated database.
- Kong is the only supported browser ingress. Frontends should not call internal service DNS names or direct pod ports.
- OutSystems remains the source of truth for credit balance. `credit-transaction-service` is the internal ledger, not the balance authority.
- `seat-inventory-service` owns seat-state transitions and exposes gRPC for latency-sensitive hold, release, sell, and status checks.
- Redis is used for ephemeral state such as purchase hold cache and verification locks, not as the primary record of business data.
- RabbitMQ carries delayed hold expiry and transfer notification work so those flows are not tied to synchronous request latency.

## Quick start

### Backend maintainer path

Double-click `start-backend.bat` from the repo root. It now:

1. checks `k8s/base/secrets.local.yaml`
2. starts Docker Desktop if needed
3. starts Minikube if needed
4. applies `k8s/base`
5. waits for StatefulSets, Deployments, and seed Jobs to finish
6. opens the Kong port-forward on `http://localhost:8000`
7. runs the Newman gateway smoke suite locally
8. optionally runs the public Cloudflare smoke suite when a tunnel token is present

### CLI equivalent

```powershell
.\scripts\start_k8s.ps1
```

If you also want the public Cloudflare smoke run:

```powershell
.\scripts\start_k8s.ps1 -RunPublicTests
```

### Manual fallback

```powershell
minikube start
kubectl apply -k k8s/base
kubectl rollout status deployment/kong -n ticketremaster-edge --timeout=300s
kubectl rollout status deployment/auth-orchestrator -n ticketremaster-core --timeout=300s
kubectl wait --for=condition=complete job --all -n ticketremaster-core --timeout=600s
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
```

Then verify:

```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli
```

## Public and local surfaces

- Local gateway: `http://localhost:8000`
- Shared public gateway: `https://ticketremasterapi.hong-yi.me`
- Local RabbitMQ management: `http://localhost:15672` after port-forwarding `svc/rabbitmq`
- Frontends should use the no-prefix routes such as `/auth/login` and `/events`
- Kong also supports `/api/...` compatibility aliases, but new frontend code should use the no-prefix form

## Browser-facing routes

| Route group | Current paths |
| --- | --- |
| Auth | `/auth/register`, `/auth/verify-registration`, `/auth/login`, `/auth/me`, `/auth/logout`, `/auth/logout-all` |
| Events and venues | `/venues`, `/events`, `/events/{eventId}`, `/events/{eventId}/seats`, `/events/{eventId}/seats/{inventoryId}`, `/admin/events`, `/admin/events/{eventId}/dashboard` |
| Credits | `/credits/balance`, `/credits/topup/initiate`, `/credits/topup/confirm`, `/credits/topup/webhook`, `/credits/transactions` |
| Purchase | `/purchase/hold/{inventoryId}`, `DELETE /purchase/hold/{inventoryId}`, `/purchase/confirm/{inventoryId}` |
| Tickets and QR | `/tickets`, `/tickets/{ticketId}/qr` |
| Marketplace | `/marketplace`, `/marketplace/list`, `DELETE /marketplace/{listingId}` |
| Transfer | `/transfer/initiate`, `/transfer/pending`, `/transfer/{transferId}`, `/transfer/{transferId}/seller-accept`, `/transfer/{transferId}/seller-reject`, `/transfer/{transferId}/buyer-verify`, `/transfer/{transferId}/seller-verify`, `/transfer/{transferId}/resend-otp`, `/transfer/{transferId}/cancel` |
| Staff verification | `/verify/scan`, `/verify/manual` |
| Stripe ingress | `/webhooks/stripe` |

## Known validation gotcha

If the gateway smoke suite shows:

- `Register` returning `400`
- followed by `Login` and other protected routes returning `401`

the usual cause is that the cluster was tested before downstream services or seed jobs were ready. The maintained startup flow now waits for the full stack before running Newman, and the gateway Postman collection now generates a fresh test email for each run.
