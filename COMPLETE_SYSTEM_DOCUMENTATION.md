# TicketRemaster Backend - Complete Documentation

## Executive Summary

TicketRemaster is a production-grade microservice backend for event ticketing, supporting seat inventory management, credit-based purchases, peer-to-peer transfers, and staff verification. The system is deployed on Kubernetes with high availability and includes advanced reliability features like distributed locks, idempotency keys, rate limiting, and graceful shutdown.

## System Architecture

### Overview

The system consists of three architectural layers:

| Layer | Namespace | Components | Purpose |
|-------|-----------|------------|---------|
| **Edge** | `ticketremaster-edge` | Cloudflare Tunnel, Kong Gateway | Public ingress, routing, rate limiting, auth |
| **Core** | `ticketremaster-core` | 8 orchestrators, 12 services, notification service | Business logic, orchestration, data processing |
| **Data** | `ticketremaster-data` | 10 PostgreSQL DBs, Redis, RabbitMQ | Persistent storage, caching, async messaging |

### Services

#### Orchestrators (8)

| Orchestrator | Port | Purpose |
|--------------|------|---------|
| `auth-orchestrator` | 8100 | User authentication, registration, JWT management |
| `event-orchestrator` | 8101 | Event discovery, venue management, seat inventory |
| `credit-orchestrator` | 8102 | Credit balance, top-ups, Stripe integration |
| `ticket-purchase-orchestrator` | 8103 | Seat holds, purchase flow, payment processing |
| `qr-orchestrator` | 8104 | QR code generation, ticket retrieval |
| `marketplace-orchestrator` | 8105 | Resale marketplace, listings |
| `transfer-orchestrator` | 8107 | P2P ticket transfers with OTP verification |
| `ticket-verification-orchestrator` | 8108 | Staff QR verification, entry management |

#### Atomic Services (12)

| Service | Purpose |
|---------|---------|
| `user-service` | User profiles, accounts, flagging |
| `venue-service` | Venue information, addresses, capacity |
| `seat-service` | Seat definitions per venue |
| `event-service` | Event CRUD, scheduling, types |
| `seat-inventory-service` | Seat availability, gRPC for holds |
| `ticket-service` | Ticket records, ownership, status |
| `ticket-log-service` | Audit trail for ticket operations |
| `marketplace-service` | Listing records, resale transactions |
| `transfer-service` | Transfer records, state machine |
| `credit-transaction-service` | Credit balance, transactions |
| `stripe-wrapper` | Stripe API abstraction |
| `otp-wrapper` | OTP generation and verification |

#### Notification Service

The `notification-service` provides real-time updates via WebSocket (Socket.IO):

- **WebSocket Server**: Port 8109 for client connections
- **Redis Pub/Sub**: For cross-service event broadcasting
- **HTTP API**: `/notifications/broadcast` for services to emit events
- **Event Types**: `seat_update`, `ticket_update`, `transfer_update`, `purchase_update`, `user_update`, `event_update`

See [services/notification-service/NOTIFICATIONS.md](services/notification-service/NOTIFICATIONS.md) for details.

## API Reference

### Authentication

All authenticated endpoints require a JWT token in the `Authorization: Bearer <token>` header.

### Key Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | Public | Register new user |
| `POST` | `/auth/login` | Public | User login |
| `GET` | `/auth/me` | JWT | Get current user profile |
| `GET` | `/events` | Public | List events |
| `GET` | `/events/{id}` | Public | Get event details |
| `POST` | `/purchase/hold` | JWT + API Key | Hold a seat |
| `POST` | `/purchase/confirm` | JWT + API Key | Complete purchase |
| `GET` | `/tickets` | JWT + API Key | Get user's tickets |
| `POST` | `/transfer/initiate` | JWT + API Key | Start P2P transfer |
| `GET` | `/verify/{qrHash}` | Staff JWT + API Key | Verify ticket at entry |

See [API.md](API.md) for complete API documentation.

## Real-time Features

### WebSocket Notifications

The notification service maintains persistent WebSocket connections with connected clients:

```javascript
// Client-side connection
const socket = io('ws://localhost:8109');

// Subscribe to events
socket.emit('subscribe', { channel: 'seat_update' });

// Listen for updates
socket.on('seat_update', (data) => {
  console.log('Seat status changed:', data);
});
```

### Event Broadcasting

Services broadcast events via HTTP:

```python
# In any service
import requests

requests.post('http://notification-service:8109/notifications/broadcast', json={
    'type': 'seat_update',
    'payload': {
        'eventId': 'evt_123',
        'seatId': 'seat_456',
        'status': 'sold'
    },
    'traceId': 'trace_abc123'
})
```

## Async Workflows (RabbitMQ)

### Seat Hold TTL

When a seat is held during purchase:
1. Message published to `seat_hold_ttl_queue` with 5-minute TTL
2. If purchase completes, message is acknowledged
3. If TTL expires, message routes to dead-letter queue for cleanup

### Seller Notifications

When a transfer is initiated:
1. Notification published to `seller_notification_queue`
2. Consumer sends email/SMS to seller
3. Decoupled from buyer's request for reliability

## Observability

### Sentry Integration

All services integrate with Sentry for:
- Error tracking and alerting
- Performance monitoring
- Distributed tracing
- Session replay (frontend)

### PostHog Integration

Frontend integrates with PostHog for:
- Product analytics
- User behavior tracking
- Session recording
- Feature flags

## Local Development

### Prerequisites

- Docker and Docker Compose
- Python 3.10+
- Node.js 20+

### Quick Start

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

### Running Tests

```bash
# Backend
cd ticketremaster-b
pytest

# Frontend
cd ticketremaster-f
npm run test
```

## Deployment

### Kubernetes

```bash
kubectl apply -k k8s/base
```

### Vercel (Frontend)

1. Connect repository to Vercel
2. Add environment variables
3. Deploy automatically on push

## Documentation

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | System overview and quickstart |
| [API.md](API.md) | Complete API reference |
| [TESTING.md](TESTING.md) | Testing guide for all components |
| [PRD.md](PRD.md) | Product requirements |
| [INSTRUCTION.md](INSTRUCTION.md) | Implementation notes |
| [OBSERVABILITY_VERIFICATION.md](OBSERVABILITY_VERIFICATION.md) | Sentry/PostHog debugging |

## Support

For issues and questions:
- Check documentation in this repository
- Review orchestrator Swagger UIs at `http://localhost:810X/apidocs`
- Contact the development team
