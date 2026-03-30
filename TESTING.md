# TicketRemaster Backend - Testing Guide

This guide covers testing the TicketRemaster backend, including local development, API testing, and deployment verification.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.10+
- Postman (optional)
- kubectl (for Kubernetes testing)

### Start the Stack

```bash
# From ticketremaster-b directory
cp .env.example .env  # Configure environment

# Start all services
docker compose up -d --build

# Check status
docker compose ps
```

### Run Migrations

```bash
# Run database migrations for all services
docker compose run --rm user-service python -m flask --app app.py db upgrade
docker compose run --rm venue-service python -m flask --app app.py db upgrade
docker compose run --rm seat-service python -m flask --app app.py db upgrade
docker compose run --rm event-service python -m flask --app app.py db upgrade
docker compose run --rm seat-inventory-service python -m flask --app app.py db upgrade
docker compose run --rm ticket-service python -m flask --app app.py db upgrade
docker compose run --rm ticket-log-service python -m flask --app app.py db upgrade
docker compose run --rm marketplace-service python -m flask --app app.py db upgrade
docker compose run --rm transfer-service python -m flask --app app.py db upgrade
docker compose run --rm credit-transaction-service python -m flask --app app.py db upgrade
```

### Seed Test Data

```bash
docker compose run --rm user-service python user_seed.py
docker compose run --rm venue-service python seed_venues.py
docker compose run --rm seat-service python seed_seats.py
docker compose run --rm event-service python seed_events.py
docker compose run --rm seat-inventory-service python seed_seat_inventory.py
```

## Unit Testing

### Run All Tests

```bash
pytest
```

### Run Tests for Specific Service

```bash
pytest services/user-service/tests/
pytest services/event-service/tests/
```

### Run with Coverage

```bash
pytest --cov=. --cov-report=html
```

## API Testing

### Using Swagger UI

Each orchestrator has a local Swagger UI:

| Orchestrator | URL |
|--------------|-----|
| auth-orchestrator | http://localhost:8100/apidocs |
| event-orchestrator | http://localhost:8101/apidocs |
| credit-orchestrator | http://localhost:8102/apidocs |
| ticket-purchase-orchestrator | http://localhost:8103/apidocs |
| qr-orchestrator | http://localhost:8104/apidocs |
| marketplace-orchestrator | http://localhost:8105/apidocs |
| transfer-orchestrator | http://localhost:8107/apidocs |
| ticket-verification-orchestrator | http://localhost:8108/apidocs |

### Using Postman

1. Import `postman/TicketRemaster.postman_collection.json`
2. Import `postman/TicketRemaster.local.postman_environment.json`
3. Select the "TicketRemaster.local" environment
4. Run requests in order

### Using curl

```bash
# Health check
curl http://localhost:8000/health

# Register user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","phoneNumber":"+1234567890"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# List events
curl http://localhost:8000/events
```

## Testing Real-time Notifications

### WebSocket Connection Test

```javascript
// In browser console or Node.js
const io = require('socket.io-client');
const socket = io('ws://localhost:8109');

socket.on('connect', () => {
  console.log('Connected to notification service');
  socket.emit('subscribe', { channel: 'seat_update' });
});

socket.on('seat_update', (data) => {
  console.log('Seat update received:', data);
});
```

### Broadcasting Test

```python
import requests

# Broadcast a test event
response = requests.post('http://localhost:8109/notifications/broadcast', json={
    'type': 'seat_update',
    'payload': {
        'eventId': 'demo-event-001',
        'seatId': 'demo-seat-001',
        'status': 'sold'
    },
    'traceId': 'test-123'
})
print(response.status_code)
```

## Testing Observability

### Sentry

```python
# In any service
import sentry_sdk
sentry_sdk.capture_message("Test message from testing")
sentry_sdk.capture_exception(ValueError("Test error"))
```

Check Sentry dashboard at https://sentry.io/ for captured events.

### PostHog (Frontend)

See frontend TESTING.md for PostHog testing.

## Infrastructure Testing

### RabbitMQ

```bash
# Check RabbitMQ is running
docker compose exec rabbitmq rabbitmq-diagnostics -q ping

# View queues
docker compose exec rabbitmq rabbitmqctl list_queues

# View exchanges
docker compose exec rabbitmq rabbitmqctl list_exchanges

# Access management UI
# Open http://localhost:15672 (guest/guest)
```

### Redis

```bash
# Check Redis is running
docker compose exec redis redis-cli ping

# View keys
docker compose exec redis redis-cli keys '*'

# Monitor commands
docker compose exec redis redis-cli monitor
```

### PostgreSQL

```bash
# List all databases
docker compose exec user-service-db psql -U ticketremaster -c '\l'

# Connect to a database
docker compose exec user-service-db psql -U ticketremaster -d user_service

# Run a query
docker compose exec user-service-db psql -U ticketremaster -d user_service -c "SELECT * FROM users LIMIT 5;"
```

## Kubernetes Testing

### Apply Manifests

```bash
# Validate manifests
kubectl kustomize .\k8s\base

# Apply to cluster
kubectl apply -k .\k8s\base
```

### Check Deployment

```bash
# Check pods
kubectl get pods -n ticketremaster-core
kubectl get pods -n ticketremaster-edge
kubectl get pods -n ticketremaster-data

# Check services
kubectl get svc -n ticketremaster-core

# Check seed jobs
kubectl get jobs -n ticketremaster-core
```

### View Logs

```bash
# Orchestrator logs
kubectl logs deployment/auth-orchestrator -n ticketremaster-core --tail=100

# Service logs
kubectl logs deployment/user-service -n ticketremaster-core --tail=100

# Follow logs
kubectl logs -f deployment/event-orchestrator -n ticketremaster-core
```

### Port Forwarding

```bash
# Forward Kong proxy
kubectl port-forward -n ticketremaster-edge svc/kong-proxy 8000:80

# Forward RabbitMQ management
kubectl port-forward -n ticketremaster-data svc/rabbitmq 15672:15672

# Forward a service directly
kubectl port-forward -n ticketremaster-core deployment/user-service 5000:5000
```

## Troubleshooting

### Service Won't Start

1. Check container logs: `docker compose logs service-name`
2. Verify environment variables: `docker compose exec service-name env | grep KEY`
3. Check database connectivity: `docker compose exec service-name python -c "import psycopg2; psycopg2.connect('...')"`

### Database Migration Errors

```bash
# Reset migrations
docker compose run --rm service-name python -m flask --app app.py db stamp head
docker compose run --rm service-name python -m flask --app app.py db migrate
docker compose run --rm service-name python -m flask --app app.py db upgrade
```

### RabbitMQ Connection Issues

```bash
# Restart RabbitMQ
docker compose restart rabbitmq

# Check queue status
docker compose exec rabbitmq rabbitmqctl list_queues name messages consumers
```

### Redis Connection Issues

```bash
# Restart Redis
docker compose restart redis

# Check memory usage
docker compose exec redis redis-cli info memory
```

## Test Checklist

Before deploying to production:

- [ ] All unit tests pass (`pytest`)
- [ ] All services start successfully (`docker compose ps`)
- [ ] Health endpoints return 200 (`curl http://localhost:8000/health`)
- [ ] Database migrations run without errors
- [ ] Seed data loads correctly
- [ ] RabbitMQ queues are created
- [ ] Redis is accessible
- [ ] Sentry test events appear in dashboard
- [ ] WebSocket notifications work
- [ ] Kubernetes manifests validate (`kubectl kustomize`)
- [ ] API documentation is accessible (Swagger UIs)

## Documentation

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | System overview |
| [API.md](API.md) | API reference |
| [COMPLETE_SYSTEM_DOCUMENTATION.md](COMPLETE_SYSTEM_DOCUMENTATION.md) | Full architecture |
| [AGENTS.md](AGENTS.md) | AI agent guidelines |
| [OBSERVABILITY_VERIFICATION.md](OBSERVABILITY_VERIFICATION.md) | Sentry/PostHog debugging |
