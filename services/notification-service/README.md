# Notification Service

Real-time notification service for TicketRemaster using WebSocket and Redis Pub/Sub.

## Features

- WebSocket connections for real-time client updates
- Redis Pub/Sub for cross-service event broadcasting
- Event channels for different domain events (seats, tickets, transfers, etc.)
- HTTP API for services to broadcast events

## Running Locally

```bash
pip install -r requirements.txt
python app.py
```

## Docker

```bash
docker build -t notification-service .
docker run -p 8109:8109 notification-service
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `JWT_SECRET` | Secret key for Socket.IO | `dev-secret` |
| `NOTIFICATION_SERVICE_HOST` | Host to bind | `0.0.0.0` |
| `NOTIFICATION_SERVICE_PORT` | Port to bind | `8109` |
| `SENTRY_DSN` | Sentry DSN | - |
| `FRONTEND_URL` | Frontend URL for CORS | `http://localhost:5173` |

## Event Types

| Event Type | Description |
|------------|-------------|
| `seat_update` | Seat status changes (available, held, sold) |
| `ticket_update` | Ticket status changes |
| `transfer_update` | Transfer status changes |
| `purchase_update` | Purchase status changes |
| `user_update` | User profile changes |
| `event_update` | Event changes |

## API Endpoints

### POST /broadcast

Broadcast an event to all connected clients.

```json
{
  "type": "seat_update",
  "payload": {
    "eventId": "evt_123",
    "seatId": "seat_456",
    "status": "sold"
  },
  "traceId": "trace_789"
}
```

### GET /stats

Get service statistics.

### GET /health

Health check endpoint.
