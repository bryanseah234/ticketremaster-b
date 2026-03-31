# TicketRemaster - Implementation Instructions

This document provides implementation guidance for deploying and maintaining the TicketRemaster system.

## System Overview

TicketRemaster is a microservice-based ticketing platform built with:
- **Frontend**: Vue 3 + TypeScript + Vite
- **Backend**: Flask microservices (8 orchestrators + 12 services)
- **Infrastructure**: Docker Compose (local), Kubernetes (production)
- **Observability**: Sentry + PostHog
- **Real-time**: WebSocket notifications via Socket.IO

## Quick Start

### Local Development

```bash
# Backend
cd ticketremaster-b
cp .env.example .env
docker compose up -d --build

# Frontend
cd ticketremaster-f
npm install
npm run dev
```

### Production Deployment

```bash
# Kubernetes
kubectl apply -k k8s/base

# Vercel (Frontend)
# Connect repository and add environment variables
```

## Architecture Decisions

### Why Microservices?

1. **Independent Scaling**: Each service scales based on its load
2. **Technology Flexibility**: Services can use different tech stacks
3. **Fault Isolation**: One service failure doesn't crash the entire system
4. **Team Autonomy**: Teams can work on services independently

### Why Flask?

1. **Rapid Development**: Quick to prototype and deploy
2. **Python Ecosystem**: Rich libraries for data processing
3. **Lightweight**: Low overhead compared to Django
4. **Easy Testing**: Simple unit and integration testing

### Why Kubernetes?

1. **Scalability**: Auto-scaling based on load
2. **Self-Healing**: Automatic restart of failed containers
3. **Service Discovery**: Built-in DNS for service communication
4. **Rolling Updates**: Zero-downtime deployments

## Key Components

### Orchestrators

Orchestrators aggregate data from multiple services for frontend consumption:

| Orchestrator | Purpose |
|--------------|---------|
| `auth-orchestrator` | Authentication and user management |
| `event-orchestrator` | Event discovery and details |
| `credit-orchestrator` | Credit balance and top-ups |
| `ticket-purchase-orchestrator` | Seat holds and purchases |
| `qr-orchestrator` | Ticket retrieval and QR codes |
| `marketplace-orchestrator` | Resale marketplace |
| `transfer-orchestrator` | P2P ticket transfers |
| `ticket-verification-orchestrator` | Staff ticket verification |

### Atomic Services

Services own a single bounded context and database:

| Service | Database | Purpose |
|---------|----------|---------|
| `user-service` | PostgreSQL | User accounts and profiles |
| `venue-service` | PostgreSQL | Venue information |
| `seat-service` | PostgreSQL | Seat definitions |
| `event-service` | PostgreSQL | Event data |
| `seat-inventory-service` | PostgreSQL + gRPC | Seat availability and holds |
| `ticket-service` | PostgreSQL | Ticket records |
| `ticket-log-service` | PostgreSQL | Audit trail |
| `marketplace-service` | PostgreSQL | Resale listings |
| `transfer-service` | PostgreSQL | Transfer records |
| `credit-transaction-service` | PostgreSQL | Credit transactions |
| `stripe-wrapper` | None | Stripe API abstraction |
| `otp-wrapper` | None | OTP generation and verification |

### Notification Service

The `notification-service` provides real-time updates via WebSocket:

- **Connection**: Socket.IO on port 8109
- **Broadcasting**: HTTP API for services to emit events
- **Pub/Sub**: Redis for cross-instance communication
- **Events**: `seat_update`, `ticket_update`, `transfer_update`, etc.

## Deployment Guide

### Environment Variables

Required variables are in `.env.example`. Key variables:

```bash
# General
APP_ENV=production
LOG_LEVEL=INFO

# Security
JWT_SECRET=<strong-random-secret>
QR_SECRET=<strong-random-secret>
QR_ENCRYPTION_KEY=<32-byte-key>

# Observability
SENTRY_DSN=https://...
SENTRY_ENVIRONMENT=production

# Database
USER_SERVICE_DATABASE_URL=postgresql://...
EVENT_SERVICE_DATABASE_URL=postgresql://...

# External Services
REDIS_URL=redis://redis:6379/0
RABBITMQ_HOST=rabbitmq
CREDIT_SERVICE_URL=https://...

# Frontend
VITE_API_BASE_URL=https://ticketremasterapi.hong-yi.me
VITE_SENTRY_DSN=https://...
VITE_POSTHOG_API_KEY=phc_...
```

### Database Migrations

```bash
# Run migrations for all services
for service in user-service venue-service seat-service event-service \
               seat-inventory-service ticket-service ticket-log-service \
               marketplace-service transfer-service credit-transaction-service; do
  docker compose run --rm $service python -m flask --app app.py db upgrade
done
```

### Seed Data

```bash
docker compose run --rm user-service python user_seed.py
docker compose run --rm venue-service python seed_venues.py
docker compose run --rm seat-service python seed_seats.py
docker compose run --rm event-service python seed_events.py
docker compose run --rm seat-inventory-service python seed_seat_inventory.py
```

### Health Checks

```bash
# Check all services
curl http://localhost:8000/health

# Check individual services
docker compose exec user-service curl http://localhost:5000/health
docker compose exec event-service curl http://localhost:5000/health
```

## Monitoring

### Sentry

All services report errors to Sentry:

```python
import sentry_sdk
sentry_sdk.capture_exception(error)
sentry_sdk.capture_message("Important event")
```

### PostHog

Frontend tracks user behavior:

```typescript
import posthog from 'posthog-js'
posthog.capture('purchase_completed', { amount: 100 })
```

### Logs

```bash
# View service logs
docker compose logs -f user-service

# Filter by level
docker compose logs --tail=100 user-service | grep ERROR
```

### Metrics

Key metrics to monitor:

- API response time (p50, p95, p99)
- Error rate by service
- Database connection pool usage
- Redis memory usage
- RabbitMQ queue depth
- WebSocket connection count

## Troubleshooting

### Service Won't Start

1. Check logs: `docker compose logs service-name`
2. Verify environment: `docker compose exec service-name env`
3. Test database connection: `docker compose exec service-name python -c "from app import db; db.engine.connect()"`

### Database Issues

```bash
# Check database status
docker compose exec user-service-db pg_isready

# View database logs
docker compose logs user-service-db

# Reset database (CAUTION: Deletes all data)
docker compose down -v
docker compose up -d user-service-db
```

### Redis Issues

```bash
# Check Redis status
docker compose exec redis redis-cli ping

# View Redis memory
docker compose exec redis redis-cli info memory

# Flush cache (CAUTION: Deletes all cache)
docker compose exec redis redis-cli flushall
```

### RabbitMQ Issues

```bash
# Check RabbitMQ status
docker compose exec rabbitmq rabbitmq-diagnostics -q ping

# List queues
docker compose exec rabbitmq rabbitmqctl list_queues

# Purge queue
docker compose exec rabbitmq rabbitmqctl purge_queue queue_name
```

## Security Considerations

### Authentication

- JWT tokens expire after 24 hours
- Refresh tokens not implemented (stateless design)
- Staff tokens include venue ID for authorization

### Rate Limiting

- Global: 50 requests/minute
- Registration: 5 requests/minute
- Login: 10 requests/minute

### Input Validation

- All inputs validated with Pydantic models
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via Vue.js auto-escaping

### Secrets Management

- Never commit secrets to version control
- Use environment variables for secrets
- Rotate secrets regularly
- Use strong random values for keys

## Performance Optimization

### Caching

- Redis for seat availability (reduces database load)
- CDN for static assets
- Browser caching for API responses

### Database

- Indexes on frequently queried columns
- Connection pooling
- Query optimization with EXPLAIN

### API

- Pagination for list endpoints
- Compression (gzip)
- HTTP/2 support

## Backup and Recovery

### Database Backups

```bash
# Backup all databases
for db in user_service venue_service seat_service event_service \
          seat_inventory_service ticket_service ticket_log_service \
          marketplace_service transfer_service credit_transaction_service; do
  docker compose exec user-service-db pg_dump -U ticketremaster $db > backups/${db}_$(date +%Y%m%d).sql
done
```

### Restore

```bash
docker compose exec -T user-service-db psql -U ticketremaster -d user_service < backup.sql
```

## Documentation

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | System overview |
| [API.md](API.md) | API reference |
| [COMPLETE_SYSTEM_DOCUMENTATION.md](COMPLETE_SYSTEM_DOCUMENTATION.md) | Full architecture |
| [TESTING.md](TESTING.md) | Testing procedures |
| [AGENTS.md](AGENTS.md) | Development guidelines |
| [PRD.md](PRD.md) | Product requirements |
