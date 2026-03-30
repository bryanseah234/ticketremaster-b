# TicketRemaster Backend - AI Agent Guidelines

This document provides guidance for AI agents working with the TicketRemaster backend codebase.

## Project Overview

TicketRemaster is a Flask-based microservice architecture for event ticketing with:
- 8 browser-facing orchestrators
- 12 atomic services and wrappers
- 1 notification service for real-time WebSocket updates
- 10 isolated PostgreSQL databases
- Redis for caching and pub/sub
- RabbitMQ for async workflows
- Kong API Gateway
- Kubernetes deployment manifests

## Key Architecture Principles

1. **Service Isolation**: Each service owns its database and is accessed only through its API
2. **Orchestrator Pattern**: Orchestrators aggregate data from multiple services for frontend consumption
3. **Async First**: Long-running operations use RabbitMQ for reliability
4. **Real-time Updates**: WebSocket notifications for immediate UI updates
5. **Idempotency**: All state-changing operations support idempotency keys
6. **Graceful Degradation**: Services handle failures with retries and circuit breakers

## Code Organization

```
ticketremaster-b/
├── api-gateway/           # Kong configuration
├── k8s/base/              # Kubernetes manifests
├── orchestrators/         # 8 orchestrator services
│   ├── auth-orchestrator/
│   ├── credit-orchestrator/
│   ├── event-orchestrator/
│   ├── marketplace-orchestrator/
│   ├── qr-orchestrator/
│   ├── ticket-purchase-orchestrator/
│   ├── ticket-verification-orchestrator/
│   └── transfer-orchestrator/
├── services/              # 12 atomic services
│   ├── credit-transaction-service/
│   ├── event-service/
│   ├── marketplace-service/
│   ├── notification-service/  # NEW: WebSocket notifications
│   ├── otp-wrapper/
│   ├── seat-inventory-service/
│   ├── seat-service/
│   ├── stripe-wrapper/
│   ├── ticket-log-service/
│   ├── ticket-service/
│   ├── transfer-service/
│   ├── user-service/
│   └── venue-service/
├── shared/                # Shared libraries
│   ├── sentry.py          # Sentry integration
│   ├── graceful_shutdown.py
│   └── requirements.txt
├── docker-compose.yml     # Local development
└── .env                   # Environment configuration
```

## Common Patterns

### Error Handling

All services use a consistent error response format:

```python
def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code
```

### Database Access

Services use SQLAlchemy with Flask-SQLAlchemy:

```python
from app import db
from models import Event

# Query
events = Event.query.filter_by(type='concert').all()

# Create
event = Event(name='Concert', date='2025-06-15')
db.session.add(event)
db.session.commit()
```

### Sentry Integration

All services initialize Sentry:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))
from sentry import init_sentry

init_sentry(service_name="my-service")
```

### Broadcasting Notifications

Services broadcast events to the notification service:

```python
import requests

def broadcast_event(event_type, payload, trace_id=None):
    requests.post('http://notification-service:8109/notifications/broadcast', json={
        'type': event_type,
        'payload': payload,
        'traceId': trace_id
    })
```

## Testing

### Unit Tests

```bash
pytest services/user-service/tests/
```

### Integration Tests

```bash
docker compose up -d
pytest --integration
```

### API Testing

Use Postman collection in `postman/` directory or Swagger UI at `http://localhost:810X/apidocs`.

## Deployment

### Local Development

```bash
docker compose up -d --build
```

### Kubernetes

```bash
kubectl apply -k k8s/base
```

### Environment Variables

Required variables are documented in `.env.example`. Key variables:
- `SENTRY_DSN` - Error tracking
- `JWT_SECRET` - Token signing
- `DATABASE_URL` - Service database connection
- `REDIS_URL` - Cache and pub/sub
- `RABBITMQ_HOST` - Message queue

## Debugging

### Check Service Health

```bash
curl http://localhost:5000/health
```

### View Logs

```bash
docker compose logs -f service-name
```

### Database Access

```bash
docker compose exec user-service-db psql -U ticketremaster -d user_service
```

### Redis CLI

```bash
docker compose exec redis redis-cli
```

## Common Issues

### Service Won't Start

1. Check `.env` file for required variables
2. Verify database is running: `docker compose ps`
3. Check logs: `docker compose logs service-name`

### Database Migration Fails

```bash
docker compose run --rm service-name python -m flask --app app.py db upgrade
```

### Sentry Not Receiving Data

1. Verify `SENTRY_DSN` is set
2. Check `sentry-sdk` is installed
3. Test with `sentry_sdk.capture_message("test")`

## Documentation

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | System overview |
| [API.md](API.md) | API reference |
| [COMPLETE_SYSTEM_DOCUMENTATION.md](COMPLETE_SYSTEM_DOCUMENTATION.md) | Full architecture |
| [TESTING.md](TESTING.md) | Testing guide |
| [services/notification-service/NOTIFICATIONS.md](services/notification-service/NOTIFICATIONS.md) | WebSocket events |
