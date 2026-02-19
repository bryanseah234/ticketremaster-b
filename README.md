# TicketRemaster Backend

> IS213 Enterprise Solution Development — Microservices-based ticketing platform

---

## Quick Start

```bash
# 1. Clone
git clone <repo-url>
cd ticketremaster-b

# 2. Configure
cp .env.example .env
# Fill in actual values in .env

# 3. Run
docker compose up --build

# 4. Dev mode (hot-reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

## Architecture

- **Orchestrator (Saga) pattern** — all flows coordinated through a central service
- **Kong API Gateway** — JWT auth, CORS, rate limiting
- **4 microservices** — Inventory (gRPC), User, Order, Event (REST)
- **RabbitMQ** — DLX-based seat auto-release on hold TTL expiry
- **4 PostgreSQL databases** — one per service, no cross-DB joins

## Documentation

| Document | Description |
|---|---|
| [INSTRUCTIONS.md](INSTRUCTIONS.md) | Full architecture reference — schemas, flows, configs |
| [API.md](API.md) | Endpoint reference with request/response contracts |
| [TASKS.md](TASKS.md) | Implementation checklist by phase |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Git workflow, code conventions, PR process |

## Services

| Service | Protocol | Port | Swagger UI |
|---|---|---|---|
| API Gateway (Kong) | HTTP | 8000 | — |
| Orchestrator | REST | 5003 | `/apidocs/` |
| User Service | REST | 5000 | `/apidocs/` |
| Order Service | REST | 5001 | `/apidocs/` |
| Event Service | REST | 5002 | `/apidocs/` |
| Inventory Service | gRPC | 50051 | — |
| RabbitMQ Management | HTTP | 15672 | — |

## Key Scenarios

1. **Ticket Purchase** — pessimistic seat locking → credit deduction → confirmation → QR generation
2. **P2P Transfer** — dual-OTP verification → atomic credit + ownership swap
3. **QR Verification** — AES-256-GCM encrypted payload → 60-second TTL → venue entry scan

## Tech Stack

- Python (Flask)
- PostgreSQL 16
- RabbitMQ 3 (DLX pattern)
- gRPC / Protocol Buffers
- Kong API Gateway
- Stripe (credit top-up)
- SMU Notification API (2FA OTP)
- Docker Compose
