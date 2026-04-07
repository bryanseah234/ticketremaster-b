# notification-service

`notification-service` is the realtime broadcast layer for TicketRemaster.

## Design role

- accepts internal HTTP broadcast requests
- emits Socket.IO events to connected clients
- uses Redis Pub/Sub so event fan-out is decoupled from the caller

## Current interfaces

### HTTP

- `GET /health`
- `POST /broadcast`
- `GET /stats`

### Socket.IO events

- `connect`
- `disconnect`
- `subscribe`
- `unsubscribe`

Supported event channels:

- `seat_update`
- `ticket_update`
- `transfer_update`
- `purchase_update`
- `user_update`
- `event_update`

## Runtime notes

- no service-owned database
- depends on Redis
- not exposed through Kong for normal browser API calls

## Local verification

```powershell
python services/notification-service/app.py
Invoke-WebRequest http://localhost:8109/health
```

Related docs:

- [NOTIFICATIONS.md](NOTIFICATIONS.md)
- [../README.md](../README.md)
