# Notification Service Documentation

This document describes when and how notifications are sent from the backend to connected clients via WebSocket.

## Overview

The notification service (`notification-service`) uses WebSocket connections and Redis Pub/Sub to broadcast real-time events to connected clients. Notifications are sent when significant state changes occur in the system.

## Event Types and Triggers

### 1. Seat Updates (`seat_update`)

**When sent:**
- When a seat is held during the purchase flow
- When a seat hold expires and the seat becomes available again
- When a seat is sold
- When seat inventory is updated by an admin

**Triggered by:**
- `ticket-purchase-orchestrator` - When a seat hold is created
- `seat-inventory-service` - When seat status changes
- `transfer-orchestrator` - When a transfer affects seat ownership

**Payload:**
```json
{
  "type": "seat_update",
  "payload": {
    "eventId": "evt_123",
    "seatId": "seat_456",
    "inventoryId": "inv_789",
    "status": "held",
    "heldUntil": "2025-03-30T10:15:00Z"
  },
  "timestamp": "2025-03-30T10:10:00Z",
  "traceId": "trace_abc123"
}
```

### 2. Ticket Updates (`ticket_update`)

**When sent:**
- When a ticket is purchased and confirmed
- When a ticket is transferred to a new owner
- When a ticket is marked as used (scanned at entry)
- When a ticket is cancelled

**Triggered by:**
- `ticket-purchase-orchestrator` - After successful purchase
- `transfer-orchestrator` - When transfer completes
- `ticket-verification-orchestrator` - When ticket is scanned

**Payload:**
```json
{
  "type": "ticket_update",
  "payload": {
    "ticketId": "tkt_123",
    "status": "valid",
    "ownerId": "user_456"
  },
  "timestamp": "2025-03-30T10:20:00Z",
  "traceId": "trace_def456"
}
```

### 3. Transfer Updates (`transfer_update`)

**When sent:**
- When a transfer is initiated
- When a transfer is accepted by the recipient
- When a transfer is declined
- When a transfer expires

**Triggered by:**
- `transfer-orchestrator` - On all transfer state changes

**Payload:**
```json
{
  "type": "transfer_update",
  "payload": {
    "transferId": "xfer_123",
    "ticketId": "tkt_456",
    "status": "pending",
    "fromUserId": "user_789",
    "toUserEmail": "recipient@example.com"
  },
  "timestamp": "2025-03-30T10:30:00Z",
  "traceId": "trace_ghi789"
}
```

### 4. Purchase Updates (`purchase_update`)

**When sent:**
- When a purchase is confirmed
- When a purchase is cancelled
- When a purchase expires (payment timeout)

**Triggered by:**
- `ticket-purchase-orchestrator` - On purchase completion or timeout

**Payload:**
```json
{
  "type": "purchase_update",
  "payload": {
    "purchaseId": "pur_123",
    "userId": "user_456",
    "eventId": "evt_789",
    "status": "confirmed",
    "totalAmount": 299.98
  },
  "timestamp": "2025-03-30T10:25:00Z",
  "traceId": "trace_jkl012"
}
```

### 5. User Updates (`user_update`)

**When sent:**
- When a user profile is updated
- When a user is flagged/unflagged by admin
- When a user's role changes

**Triggered by:**
- `user-service` - On profile changes
- `auth-orchestrator` - On admin actions

**Payload:**
```json
{
  "type": "user_update",
  "payload": {
    "userId": "user_123",
    "email": "user@example.com",
    "isFlagged": false,
    "role": "user"
  },
  "timestamp": "2025-03-30T10:35:00Z",
  "traceId": "trace_mno345"
}
```

### 6. Event Updates (`event_update`)

**When sent:**
- When an event is created
- When an event is updated
- When an event is cancelled
- When an event is published

**Triggered by:**
- `event-service` - On event CRUD operations
- `event-orchestrator` - On admin actions

**Payload:**
```json
{
  "type": "event_update",
  "payload": {
    "eventId": "evt_123",
    "name": "Concert Name",
    "date": "2025-06-15T19:30:00Z",
    "status": "published"
  },
  "timestamp": "2025-03-30T10:40:00Z",
  "traceId": "trace_pqr678"
}
```

## WebSocket Connection

### Connecting

```typescript
import { io } from 'socket.io-client'

const socket = io(import.meta.env.VITE_WS_URL || 'ws://localhost:8109')

socket.on('connect', () => {
  console.log('Connected to notification service')
})
```

### Subscribing to Events

```typescript
// Subscribe to a specific event type
socket.emit('subscribe', { channel: 'seat_update' })

// Listen for events
socket.on('seat_update', (data) => {
  console.log('Seat updated:', data)
})
```

### Unsubscribing

```typescript
socket.emit('unsubscribe', { channel: 'seat_update' })
```

## HTTP Broadcast API

Services can broadcast events via HTTP:

```http
POST /notifications/broadcast
Content-Type: application/json
apikey: your-api-key

{
  "type": "seat_update",
  "payload": {
    "eventId": "evt_123",
    "seatId": "seat_456",
    "status": "sold"
  },
  "traceId": "trace_xyz"
}
```

## Frontend Integration

The `useWebSocket` composable handles connection and subscription:

```typescript
import { useWebSocket } from '@/composables/useWebSocket'

const { state, subscribe, unsubscribe } = useWebSocket()

// Subscribe to seat updates
const unsub = subscribe('seat_update', (message) => {
  console.log('Seat update:', message.payload)
})

// Cleanup
onUnmounted(() => {
  unsub()
})
```

## Demo Mode

When the backend is unavailable, the frontend enters demo mode and mock data is used instead of real-time updates. In demo mode:
- WebSocket connection attempts are skipped
- UI shows a banner indicating demo mode
- State-changing actions are disabled
- Read-only views show mock data

To manually enable demo mode for UI development:
```
https://your-app.vercel.app?demo=true
```

Or visit `/demo-login` to log in with a demo account.

## Troubleshooting

### Notifications not appearing?

1. Check WebSocket connection in browser dev tools → Network tab
2. Verify `VITE_WS_URL` environment variable is correct
3. Check notification service logs: `docker logs ticketremaster-notification-service-1`
4. Verify Redis is running: `docker exec ticketremaster-redis-1 redis-cli ping`

### Events not triggering notifications?

1. Check that the service is calling the broadcast endpoint
2. Verify the event type is registered in `notification-service/app.py`
3. Check Redis Pub/Sub: `docker exec ticketremaster-redis-1 redis-cli SUBSCRIBE notifications:*`
