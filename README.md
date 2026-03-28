# TicketRemaster Backend

## Project Overview
TicketRemaster is an advanced, microservices-oriented backend platform providing end-to-end ticketing operations. It facilitates event management, real-time seat inventory holding (via gRPC and pessimistic locking), dynamic QR-code verification, a secure peer-to-peer marketplace, and a credit-based payment ecosystem. The architecture is composed of domain-specific atomic Flask services orchestrated by dedicated edge APIs, utilizing RabbitMQ for asynchronous event processing and PostgreSQL for isolated data persistence.

## Prerequisites
To run and develop TicketRemaster locally, ensure the following are installed:
- **Docker & Docker Compose:** For containerization and orchestration.
- **Python 3.12+:** For running local scripts or virtual environments.
- **Stripe CLI:** Required for forwarding webhooks during local payment testing.
- **Postman:** For executing the provided E2E API test collections.

## Environment Configuration
The system relies on an extensive set of environment variables. Create a `.env` file in the repository root (use `.env.example` as a template). Key variables include:

### Security & Secrets (Do not expose)
- `JWT_SECRET`: Secret key for signing JSON Web Tokens.
- `QR_SECRET`: Seed key for generating SHA-256 hashed dynamic QR codes.
- `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET`: Keys for Stripe payment intents and webhook verification.
- `OUTSYSTEMS_API_KEY`: Authentication key for the external Credit Service.
- `SMU_API_KEY`: Authentication key for the external SMU OTP Notification service.

### System & Infrastructure
- `SEAT_HOLD_DURATION_SECONDS`: Integer defining seat hold TTL (e.g., `600` for production, `10` for testing).
- `RABBITMQ_HOST`, `RABBITMQ_USER`, `RABBITMQ_PASS`: Credentials for the message broker.
- `*_SERVICE_DATABASE_URL`: PostgreSQL connection strings for each atomic service (e.g., `postgresql://ticketremaster:change_me@user-service-db:5432/user_service`).
- `*_URL`: Internal routing URLs for service-to-service and orchestrator communication.

## Installation & Setup
The repository includes an automated script to build the containers, execute SQLAlchemy migrations, and seed baseline data.

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd ticketremaster
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Update .env with any necessary local overrides and keys
   ```

3. **Build, Migrate, and Seed:**
   Execute the provided setup script. Use the `--fresh` flag to wipe existing Docker volumes and start clean.
   ```bash
   bash scripts/start_and_seed.sh --fresh
   ```
   *Note: This script orchestrates `docker compose up --build`, runs `flask db upgrade` across all 10 databases, and executes the necessary Python seed scripts to populate venues, seats, events, and inventory.*

## Usage & Workflows
Once the stack is successfully deployed, the following core interfaces are exposed:
- **Kong API Gateway:** `http://localhost:8000` — All frontend HTTP requests should be routed here.
- **RabbitMQ Management UI:** `http://localhost:15672` (Credentials: `guest` / `guest`) — Useful for monitoring the `seat-hold-dlx` and `seller_notification_queue`.

### Common Workflows
- **Stripe Webhook Testing:**
  ```bash
  stripe listen --forward-to localhost:5011/stripe/webhook
  ```
- **Manual Database Inspection:**
  ```bash
  docker compose exec <service-name>-db psql -U ticketremaster -d <db_name>
  ```
- **Service Logs:**
  ```bash
  docker compose logs -f ticket-purchase-orchestrator
  ```

## Testing & Deployment
### Local Testing
- **Unit Tests:** Each atomic service and orchestrator contains a `tests/` directory utilizing `pytest`. Run them inside the container:
  ```bash
  docker compose run --rm user-service pytest
  ```
- **E2E Integration:** Import `postman/TicketRemaster.postman_collection.json` and `postman/TicketRemaster.local.postman_environment.json` into Postman to execute comprehensive business journey scenarios.

### Deployment (Kubernetes)
The platform is designed for a Kubernetes deployment (Phase 8). Base manifests can be generated via Kompose:
```bash
kompose convert -f docker-compose.yml -o k8s/
```
Production deployments require configuring `HorizontalPodAutoscaler` for high-throughput services (e.g., `seat-inventory-service`), migrating `.env` values to Kubernetes Secrets, and adjusting service definitions from `NodePort` to `ClusterIP` behind an Ingress controller.

---

## Documentation Hub

Use this section as the starting point. All major docs are cross-linked below.

### Project-level docs
- [TESTING.md](TESTING.md) — full testing playbook, Postman flow, external integration checks, troubleshooting
- [DESIGN.md](DESIGN.md) — architecture and design context
- [INSTRUCTION.md](INSTRUCTION.md) — implementation guide and engineering rules
- [TASK.md](TASK.md) — phase-by-phase execution checklist and status
- [FRONTEND.md](FRONTEND.md) — frontend contract and orchestrator-facing API plan
- [OUTSYSTEMS.md](OUTSYSTEMS.md) — OutSystems integration reference

### Collections and environments
- [postman/README.md](postman/README.md) — Postman asset usage, seeded-variable assumptions, and chaining notes
- [postman/TicketRemaster.postman_collection.json](postman/TicketRemaster.postman_collection.json) — shared collection
- [postman/TicketRemaster.local.postman_environment.json](postman/TicketRemaster.local.postman_environment.json) — local environment

### Service-level docs
- [services/README.md](services/README.md) — service index and where each service guide lives
- [services/user-service/README.md](services/user-service/README.md)
- [services/venue-service/README.md](services/venue-service/README.md)
- [services/seat-service/README.md](services/seat-service/README.md)
- [services/event-service/README.md](services/event-service/README.md)
- [services/seat-inventory-service/README.md](services/seat-inventory-service/README.md)
- [services/ticket-service/README.md](services/ticket-service/README.md)
- [services/ticket-log-service/README.md](services/ticket-log-service/README.md)
- [services/marketplace-service/README.md](services/marketplace-service/README.md)
- [services/transfer-service/README.md](services/transfer-service/README.md)
- [services/credit-transaction-service/README.md](services/credit-transaction-service/README.md)
- [services/stripe-wrapper/README.md](services/stripe-wrapper/README.md)
- [services/otp-wrapper/README.md](services/otp-wrapper/README.md)

### Orchestrator docs
- [orchestrators/README.md](orchestrators/README.md) — orchestrator index and implementation status
- [orchestrators/auth-orchestrator/README.md](orchestrators/auth-orchestrator/README.md)
- [orchestrators/event-orchestrator/README.md](orchestrators/event-orchestrator/README.md)
- [orchestrators/credit-orchestrator/README.md](orchestrators/credit-orchestrator/README.md)
- [orchestrators/ticket-purchase-orchestrator/README.md](orchestrators/ticket-purchase-orchestrator/README.md)
- [orchestrators/qr-orchestrator/README.md](orchestrators/qr-orchestrator/README.md)
- [orchestrators/marketplace-orchestrator/README.md](orchestrators/marketplace-orchestrator/README.md)
- [orchestrators/transfer-orchestrator/README.md](orchestrators/transfer-orchestrator/README.md)
- [orchestrators/ticket-verification-orchestrator/README.md](orchestrators/ticket-verification-orchestrator/README.md)

### Shared scaffolding docs
- [templates/README.md](templates/README.md) — Dockerfile scaffolding templates and copy map
- [shared/README.md](shared/README.md) — reusable dependencies and generated artifacts
- [shared/grpc/README.md](shared/grpc/README.md) — gRPC stub generation and copy rules

### Internal implementation skills
- [.github/skills/flask-service/SKILL.md](.github/skills/flask-service/SKILL.md)
- [.github/skills/orchestrator-flow/SKILL.md](.github/skills/orchestrator-flow/SKILL.md)
- [.github/skills/grpc-service/SKILL.md](.github/skills/grpc-service/SKILL.md)
- [.github/skills/database-models/SKILL.md](.github/skills/database-models/SKILL.md)
- [.github/skills/error-handling/SKILL.md](.github/skills/error-handling/SKILL.md)
- [.github/skills/qr-encryption/SKILL.md](.github/skills/qr-encryption/SKILL.md)

## Stripe and OTP Quick Navigation

- Stripe manual/automated testing: [TESTING.md](TESTING.md) and [services/stripe-wrapper/README.md](services/stripe-wrapper/README.md)
- OTP manual/automated testing: [TESTING.md](TESTING.md) and [services/otp-wrapper/README.md](services/otp-wrapper/README.md)

## Recommended Reading Order

1. [TESTING.md](TESTING.md)  
2. [postman/README.md](postman/README.md)  
3. [services/README.md](services/README.md)  
4. [services/stripe-wrapper/README.md](services/stripe-wrapper/README.md) and [services/otp-wrapper/README.md](services/otp-wrapper/README.md)  
5. [TASK.md](TASK.md) and [INSTRUCTION.md](INSTRUCTION.md)
