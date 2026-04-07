# Notification Service Event Notes

This file documents the event model implemented by `notification-service`.

## Transport model

- services publish an HTTP request to `POST /broadcast`
- the notification service republishes the payload to Redis Pub/Sub
- Socket.IO clients subscribed to that channel receive the event

The event envelope is:

```json
{
  "type": "seat_update",
  "payload": {},
  "timestamp": "2026-04-07T12:00:00+00:00",
  "traceId": "trace_123"
}
```

## Supported channels

### `seat_update`

Used for seat hold, release, or sale state changes.

### `ticket_update`

Used for ticket ownership or lifecycle changes such as purchase, transfer completion, or check-in.

### `transfer_update`

Used for transfer status changes across buyer and seller steps.

### `purchase_update`

Used for purchase completion or failure events.

### `user_update`

Reserved for user profile or moderation state changes.

### `event_update`

Reserved for event creation, update, or cancellation broadcasts.

## Socket.IO usage

Subscribe:

```javascript
socket.emit('subscribe', { channel: 'seat_update' });
```

Receive:

```javascript
socket.on('seat_update', (message) => {
  console.log(message);
});
```

Unsubscribe:

```javascript
socket.emit('unsubscribe', { channel: 'seat_update' });
```

## Internal HTTP usage

```json
{
  "type": "transfer_update",
  "payload": {
    "transferId": "txr_001",
    "status": "pending_seller_acceptance"
  },
  "traceId": "trace_abc"
}
```

## Operational note

The service is currently internal-only and depends on Redis. If Redis is unavailable, broadcast reliability is degraded even though the HTTP endpoint itself may still answer.
