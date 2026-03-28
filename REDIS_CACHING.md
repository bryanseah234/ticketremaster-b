# Redis Hold Caching — Implementation Guide

## What This Does

Adds Redis as an in-memory cache for seat hold status. When the ticket purchase
orchestrator needs to verify a seat is still held before confirming a purchase, it reads
from Redis instead of making a gRPC call to the seat inventory service and hitting
the database.

```
Before:  POST /purchase/confirm → gRPC GetSeatStatus → PostgreSQL query → response
After:   POST /purchase/confirm → Redis GET (cache hit) → response
                                → Redis miss → gRPC GetSeatStatus → PostgreSQL → response
```

Redis responds in under 1ms. gRPC + DB takes 5–50ms. Under high load during a
popular event sale, this significantly reduces latency and database pressure.

## How gRPC and Redis Work Together

Redis does NOT replace gRPC. They serve different purposes:

| Operation | gRPC | Redis |
|---|---|---|
| `HoldSeat` | Pessimistic DB lock — ensures only one buyer succeeds | Writes cache after DB commit |
| `ReleaseSeat` | Clears DB record | Deletes cache key |
| `SellSeat` | Marks DB record as sold | Deletes cache key |
| `GetSeatStatus` | DB fallback when cache misses | Fast read for cache hits |

gRPC remains the source of truth. Redis is read-only from the orchestrator's perspective.

---

## Files to Change

| File | What Changes |
|---|---|
| `docker-compose.yml` | Add Redis service, `REDIS_URL` env var to 2 containers, `redis-data` volume |
| `services/seat-inventory-service/requirements.txt` | Add `redis==5.0.1` |
| `services/seat-inventory-service/grpc_server.py` | Write/clear cache after every DB state change |
| `orchestrators/ticket-purchase-orchestrator/requirements.txt` | Add `redis==5.0.1` |
| `orchestrators/ticket-purchase-orchestrator/routes.py` | Read from Redis in `confirm_purchase` |

---

## Step 1 — docker-compose.yml

### 1a. Add Redis service

Add under `services:`, alongside your other services:

```yaml
redis:
  image: redis:7-alpine
  restart: unless-stopped
  networks:
    - ticketremaster
  ports:
    - "6379:6379"
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 5s
    retries: 5
  volumes:
    - redis-data:/data
```

### 1b. Add redis-data volume

At the bottom of `docker-compose.yml` under `volumes:`:

```yaml
volumes:
  ...existing volumes...
  redis-data:
```

### 1c. Add REDIS_URL to seat-inventory-service

```yaml
seat-inventory-service:
  environment:
    SEAT_INVENTORY_SERVICE_DATABASE_URL: ${SEAT_INVENTORY_SERVICE_DATABASE_URL}
    SEAT_INVENTORY_GRPC_PORT: ${SEAT_INVENTORY_GRPC_PORT:-50051}
    REDIS_URL: redis://redis:6379/0        # ← add this
  depends_on:
    seat-inventory-service-db:
      condition: service_healthy
    redis:                                  # ← add this
      condition: service_healthy            # ← add this
```

### 1d. Add REDIS_URL to ticket-purchase-orchestrator

```yaml
ticket-purchase-orchestrator:
  environment:
    ...existing env vars...
    REDIS_URL: redis://redis:6379/0        # ← add this
  depends_on:
    ...existing depends_on...
    redis:                                  # ← add this
      condition: service_healthy            # ← add this
```

---

## Step 2 — seat-inventory-service/requirements.txt

Add one line:

```
redis==5.0.1
```

---

## Step 3 — seat-inventory-service/grpc_server.py

Replace the entire file with the following. The only additions compared to your
current file are the Redis helper functions and the `_cache_hold` / `_clear_hold`
calls after each DB commit:

```python
import json
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta

import redis as redis_lib

from app import create_app, db
from models import SeatInventory
from seat_inventory_pb2 import (
    GetSeatStatusResponse,
    HoldSeatResponse,
    ReleaseSeatResponse,
    SellSeatResponse,
)
from seat_inventory_pb2_grpc import SeatInventoryServiceServicer

logger = logging.getLogger(__name__)


# ── Redis helpers ─────────────────────────────────────────────────────────────

def _get_redis():
    """Return a Redis client. Returns None silently if Redis is unavailable."""
    try:
        client = redis_lib.from_url(
            os.environ.get("REDIS_URL", "redis://redis:6379/0"),
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis unavailable: %s — proceeding without cache", exc)
        return None


def _cache_hold(inventory_id, user_id, hold_token, held_until_iso, ttl_seconds):
    """Write hold status to Redis with TTL matching the hold duration."""
    r = _get_redis()
    if not r:
        return
    try:
        r.setex(
            f"hold:{inventory_id}",
            int(ttl_seconds),
            json.dumps({
                "status":       "held",
                "heldByUserId": user_id,
                "holdToken":    hold_token,
                "heldUntil":    held_until_iso,
            }),
        )
        logger.info("Redis: cached hold for %s (TTL=%ds)", inventory_id, ttl_seconds)
    except Exception as exc:
        logger.warning("Redis cache write failed: %s", exc)


def _clear_hold(inventory_id):
    """Delete hold key from Redis when seat is released or sold."""
    r = _get_redis()
    if not r:
        return
    try:
        r.delete(f"hold:{inventory_id}")
        logger.info("Redis: cleared hold for %s", inventory_id)
    except Exception as exc:
        logger.warning("Redis cache delete failed: %s", exc)


# ── gRPC service ──────────────────────────────────────────────────────────────

class SeatInventoryGrpcService(SeatInventoryServiceServicer):
    def __init__(self, flask_app=None):
        self.app = flask_app or create_app()

    def HoldSeat(self, request, context):
        with self.app.app_context():
            now          = datetime.now(UTC)
            hold_seconds = request.hold_duration_seconds if request.hold_duration_seconds > 0 else 600
            held_until   = now + timedelta(seconds=hold_seconds)
            hold_token   = str(uuid.uuid4())

            locked_row = (
                db.session.query(SeatInventory)
                .filter(SeatInventory.inventoryId == request.inventory_id)
                .with_for_update()
                .one_or_none()
            )

            if not locked_row:
                db.session.rollback()
                return HoldSeatResponse(
                    success=False, status='not_found', held_until='',
                    error_code='INVENTORY_NOT_FOUND', hold_token='',
                )

            if locked_row.status != 'available':
                db.session.rollback()
                return HoldSeatResponse(
                    success=False,
                    status=locked_row.status,
                    held_until=locked_row.heldUntil.isoformat() if locked_row.heldUntil else '',
                    error_code='SEAT_NOT_AVAILABLE',
                    hold_token='',
                )

            updated_rows = (
                db.session.query(SeatInventory)
                .filter(
                    SeatInventory.inventoryId == request.inventory_id,
                    SeatInventory.status == 'available',
                )
                .update(
                    {
                        SeatInventory.status:       'held',
                        SeatInventory.heldByUserId: request.user_id,
                        SeatInventory.holdToken:    hold_token,
                        SeatInventory.heldUntil:    held_until,
                    },
                    synchronize_session=False,
                )
            )

            if updated_rows != 1:
                db.session.rollback()
                latest = db.session.get(SeatInventory, request.inventory_id)
                return HoldSeatResponse(
                    success=False,
                    status=latest.status if latest else 'not_found',
                    held_until=latest.heldUntil.isoformat() if latest and latest.heldUntil else '',
                    error_code='SEAT_NOT_AVAILABLE',
                    hold_token='',
                )

            db.session.commit()

            # Write to Redis after successful DB commit
            _cache_hold(
                inventory_id=request.inventory_id,
                user_id=request.user_id,
                hold_token=hold_token,
                held_until_iso=held_until.isoformat(),
                ttl_seconds=hold_seconds,
            )

            return HoldSeatResponse(
                success=True, status='held',
                held_until=held_until.isoformat(),
                error_code='', hold_token=hold_token,
            )

    def ReleaseSeat(self, request, context):
        with self.app.app_context():
            inventory = (
                db.session.query(SeatInventory)
                .filter(SeatInventory.inventoryId == request.inventory_id)
                .with_for_update()
                .one_or_none()
            )

            if (
                not inventory
                or inventory.status != 'held'
                or inventory.heldByUserId != request.user_id
                or inventory.holdToken != request.hold_token
            ):
                db.session.rollback()
                return ReleaseSeatResponse(success=False)

            inventory.status       = 'available'
            inventory.heldByUserId = None
            inventory.holdToken    = None
            inventory.heldUntil    = None
            db.session.commit()

            # Clear Redis cache after successful release
            _clear_hold(request.inventory_id)

            return ReleaseSeatResponse(success=True)

    def SellSeat(self, request, context):
        with self.app.app_context():
            inventory = (
                db.session.query(SeatInventory)
                .filter(SeatInventory.inventoryId == request.inventory_id)
                .with_for_update()
                .one_or_none()
            )

            if not inventory:
                db.session.rollback()
                return SellSeatResponse(success=False)

            if (
                inventory.status != 'held'
                or inventory.heldByUserId != request.user_id
                or inventory.holdToken != request.hold_token
            ):
                db.session.rollback()
                return SellSeatResponse(success=False)

            inventory.status       = 'sold'
            inventory.heldByUserId = None
            inventory.holdToken    = None
            inventory.heldUntil    = None
            db.session.commit()

            # Clear Redis cache after successful sale
            _clear_hold(request.inventory_id)

            return SellSeatResponse(success=True)

    def GetSeatStatus(self, request, context):
        with self.app.app_context():
            # Try Redis first
            r = _get_redis()
            if r:
                try:
                    cached = r.get(f"hold:{request.inventory_id}")
                    if cached:
                        data = json.loads(cached)
                        logger.info("Redis: cache hit for GetSeatStatus %s", request.inventory_id)
                        return GetSeatStatusResponse(
                            inventory_id=request.inventory_id,
                            status=data["status"],
                            held_until=data.get("heldUntil", ""),
                        )
                except Exception as exc:
                    logger.warning("Redis read failed, falling back to DB: %s", exc)

            # Cache miss or Redis unavailable — fall back to DB
            logger.info("Redis: cache miss for GetSeatStatus %s — querying DB", request.inventory_id)
            inventory = db.session.get(SeatInventory, request.inventory_id)
            if not inventory:
                return GetSeatStatusResponse(
                    inventory_id=request.inventory_id, status='not_found', held_until='',
                )
            return GetSeatStatusResponse(
                inventory_id=inventory.inventoryId,
                status=inventory.status,
                held_until=inventory.heldUntil.isoformat() if inventory.heldUntil else '',
            )
```

---

## Step 4 — ticket-purchase-orchestrator/requirements.txt

Add one line:

```
redis==5.0.1
```

---

## Step 5 — ticket-purchase-orchestrator/routes.py

### 5a. Add Redis import and client at the top of the file

After the existing imports, add:

```python
import redis as redis_lib

_redis_client = None


def _get_redis():
    """Return a cached Redis client. Returns None if Redis is unavailable."""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None
    try:
        client = redis_lib.from_url(
            os.environ.get("REDIS_URL", "redis://redis:6379/0"),
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        _redis_client = client
        return client
    except Exception as exc:
        logger.warning("Redis unavailable: %s — falling back to gRPC", exc)
        return None
```

### 5b. Replace the seat status check in confirm_purchase

In the `confirm_purchase` function, find this block:

```python
# 1. Verify seat is still held (fast gRPC check)
try:
    stub        = _grpc_stub()
    seat_status = stub.GetSeatStatus(
        seat_inventory_pb2.GetSeatStatusRequest(inventory_id=inventory_id)
    )
except grpc.RpcError as exc:
    logger.error("gRPC GetSeatStatus error: %s", exc)
    return _error("SERVICE_UNAVAILABLE", "Seat inventory service unavailable.", 503)

if seat_status.status != "held":
    code = "PAYMENT_HOLD_EXPIRED" if seat_status.status == "available" else "SEAT_UNAVAILABLE"
    return _error(code, "Seat is no longer held. Please re-select.", 410 if code == "PAYMENT_HOLD_EXPIRED" else 409)

if seat_status.held_until:
    try:
        held_until = datetime.fromisoformat(seat_status.held_until.replace("Z", "+00:00"))
        if held_until.tzinfo is None:
            held_until = held_until.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > held_until:
            return _error("PAYMENT_HOLD_EXPIRED", "Seat hold has expired. Please re-select.", 410)
    except ValueError:
        pass
```

Replace it with:

```python
# 1. Verify seat is still held — check Redis first, fall back to gRPC
held_until_str = None
r = _get_redis()
if r:
    try:
        cached = r.get(f"hold:{inventory_id}")
        if cached:
            hold_data      = json.loads(cached)
            held_until_str = hold_data.get("heldUntil", "")
            logger.info("Redis: cache hit for hold check on %s", inventory_id)
        else:
            # Cache miss — seat is not held or hold expired
            logger.info("Redis: cache miss for %s — falling back to gRPC", inventory_id)
    except Exception as exc:
        logger.warning("Redis read error: %s — falling back to gRPC", exc)
        cached = None

# Fall back to gRPC if Redis missed or was unavailable
if not r or not cached:
    try:
        stub        = _grpc_stub()
        seat_status = stub.GetSeatStatus(
            seat_inventory_pb2.GetSeatStatusRequest(inventory_id=inventory_id)
        )
    except grpc.RpcError as exc:
        logger.error("gRPC GetSeatStatus error: %s", exc)
        return _error("SERVICE_UNAVAILABLE", "Seat inventory service unavailable.", 503)

    if seat_status.status != "held":
        code = "PAYMENT_HOLD_EXPIRED" if seat_status.status == "available" else "SEAT_UNAVAILABLE"
        return _error(code, "Seat is no longer held. Please re-select.", 410 if code == "PAYMENT_HOLD_EXPIRED" else 409)

    held_until_str = seat_status.held_until

# Validate TTL
if held_until_str:
    try:
        held_until = datetime.fromisoformat(held_until_str.replace("Z", "+00:00"))
        if held_until.tzinfo is None:
            held_until = held_until.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > held_until:
            return _error("PAYMENT_HOLD_EXPIRED", "Seat hold has expired. Please re-select.", 410)
    except ValueError:
        pass

stub = _grpc_stub()
```

> **Note:** The last line `stub = _grpc_stub()` ensures the gRPC stub is always
> available for the `SellSeat` call later in the function even when the status
> check was served from Redis.

---

## Step 6 — Rebuild and verify

```bash
docker compose up --build -d seat-inventory-service ticket-purchase-orchestrator
```

Verify Redis is running:

```bash
docker compose ps redis
```

Verify the cache is working by holding a seat and checking Redis:

```bash
docker compose exec redis redis-cli keys "hold:*"
```

You should see a key like `hold:787b91c8-a35b-4e91-b75f-1f7c5725591b` appear after
holding a seat. It disappears automatically when the hold expires or the purchase
is confirmed.

Check the TTL on the key:

```bash
docker compose exec redis redis-cli ttl "hold:787b91c8-a35b-4e91-b75f-1f7c5725591b"
```

Should return the number of seconds remaining on the hold.

---

## Failure behaviour

Redis failures are always handled gracefully — the code never crashes if Redis is
down. Every Redis call is wrapped in a try/except that falls back to the existing
gRPC path. This means:

- Redis goes down → system works normally, slightly slower
- Redis comes back up → caching resumes automatically
- Redis has stale data → TTL ensures stale keys expire naturally

The database and gRPC remain the authoritative source of truth at all times.
