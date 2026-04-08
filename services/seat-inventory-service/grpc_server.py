import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any
import uuid
import time
import random

import redis
import sqlalchemy.exc

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


def _get_redis_client():
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return None
    try:
        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis unavailable for seat hold caching: %s", exc)
        return None


def _log_cache_invalidation_failure(inventory_id: str, error: str) -> None:
    """
    Log cache invalidation failure to DLQ for manual intervention.
    This ensures operations team is aware of the issue.
    """
    try:
        # Try to publish to DLQ via RabbitMQ
        import pika
        
        message = json.dumps({
            "event": "cache_invalidation_failed",
            "inventory_id": inventory_id,
            "cache_key": f"hold:{inventory_id}",
            "error": error,
            "timestamp": datetime.now(UTC).isoformat(),
            "service": "seat-inventory-service",
        })
        
        conn = pika.BlockingConnection(pika.ConnectionParameters(
            host=os.environ.get("RABBITMQ_HOST", "rabbitmq"),
            port=int(os.environ.get("RABBITMQ_PORT", "5672")),
            credentials=pika.PlainCredentials(
                os.environ.get("RABBITMQ_USER", "guest"),
                os.environ.get("RABBITMQ_PASS", "guest"),
            ),
            connection_attempts=2,
            retry_delay=1,
        ))
        ch = conn.channel()
        ch.basic_publish(
            exchange="",
            routing_key="cache_invalidation_dlq",
            body=message,
            properties=pika.BasicProperties(delivery_mode=2),
        )
        conn.close()
        logger.info("Cache invalidation failure logged to DLQ for inventory %s", inventory_id)
    except Exception as exc:
        logger.error("Failed to log cache invalidation failure to DLQ for %s: %s", inventory_id, exc)


def _write_hold_cache(
    inventory_id: str,
    user_id: str,
    hold_token: str,
    held_until_iso: str,
    ttl_seconds: int,
) -> None:
    client = _get_redis_client()
    if client is None:
        return
    payload: dict[str, Any] = {
        "status": "held",
        "heldByUserId": user_id,
        "holdToken": hold_token,
        "heldUntil": held_until_iso,
    }
    try:
        client.setex(f"hold:{inventory_id}", ttl_seconds, json.dumps(payload))
    except Exception as exc:
        logger.warning("Redis hold cache write failed for %s: %s", inventory_id, exc)


def _delete_hold_cache(inventory_id: str) -> None:
    """
    Delete hold cache with retry logic.
    Retries up to CACHE_RETRY_ATTEMPTS times with exponential backoff.
    If all retries fail, logs warning and sends to DLQ for manual intervention.
    """
    client = _get_redis_client()
    if client is None:
        logger.warning("Redis unavailable for cache invalidation of %s", inventory_id)
        return
    
    cache_key = f"hold:{inventory_id}"
    last_error = None
    
    for attempt in range(CACHE_RETRY_ATTEMPTS):
        try:
            result = client.delete(cache_key)
            if result:
                logger.info("Cache deleted successfully for inventory %s", inventory_id)
                return
            else:
                # Key didn't exist, which is fine
                logger.info("Cache key did not exist for inventory %s", inventory_id)
                return
        except Exception as exc:
            if attempt < CACHE_RETRY_ATTEMPTS - 1:
                delay = (CACHE_RETRY_DELAY_MS / 1000) * (2 ** attempt)
                logger.warning(
                    "Cache delete failed for inventory %s (attempt %d/%d). Retrying in %.1fs... Error: %s",
                    inventory_id, attempt + 1, CACHE_RETRY_ATTEMPTS, delay, exc
                )
                time.sleep(delay)
            else:
                logger.error(
                    "Cache delete failed for inventory %s after %d attempts: %s",
                    inventory_id, CACHE_RETRY_ATTEMPTS, exc
                )
                # Log to DLQ for manual intervention
                _log_cache_invalidation_failure(inventory_id, str(exc))


def _check_idempotency(key: str) -> dict | None:
    """
    Check if operation was already processed (idempotency check).
    Returns cached result if found, None otherwise.
    """
    client = _get_redis_client()
    if client is None:
        return None
    try:
        cached = client.get(f"idempotent:{key}")
        if cached:
            logger.info("Idempotency cache hit for key: %s", key)
            return json.loads(cached)
    except Exception as exc:
        logger.warning("Idempotency check failed for key %s: %s", key, exc)
    return None


def _cache_idempotency_result(key: str, result: Any, ttl: int = 3600) -> None:
    """
    Cache operation result for idempotency.
    TTL defaults to 1 hour.
    """
    client = _get_redis_client()
    if client is None:
        return
    try:
        client.setex(f"idempotent:{key}", ttl, json.dumps(result))
    except Exception as exc:
        logger.warning("Failed to cache idempotency result for key %s: %s", key, exc)


# Deadlock retry configuration
MAX_DEADLOCK_RETRIES = int(os.environ.get("MAX_DEADLOCK_RETRIES", "3"))
DEADLOCK_BASE_DELAY_MS = int(os.environ.get("DEADLOCK_BASE_DELAY_MS", "100"))

# Cache invalidation retry configuration
CACHE_RETRY_ATTEMPTS = int(os.environ.get("CACHE_RETRY_ATTEMPTS", "3"))
CACHE_RETRY_DELAY_MS = int(os.environ.get("CACHE_RETRY_DELAY_MS", "1000"))


def _is_deadlock_error(exc):
    """Check if exception is a database deadlock."""
    if isinstance(exc, sqlalchemy.exc.OperationalError):
        orig = exc.orig
        # PostgreSQL deadlock error code is 40P01
        if hasattr(orig, 'pgcode') and orig.pgcode == '40P01':
            return True
        # Generic deadlock detection
        if 'deadlock' in str(orig).lower():
            return True
    return False


def _calculate_deadlock_delay(attempt):
    """Calculate exponential backoff delay with jitter for deadlock retry."""
    base_delay = DEADLOCK_BASE_DELAY_MS / 1000.0  # Convert to seconds
    delay = base_delay * (2 ** attempt)
    jitter = random.uniform(0, base_delay * 0.5)
    return delay + jitter


def _normalize_timestamp(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _hold_has_expired(inventory: SeatInventory, now: datetime) -> bool:
    if inventory.status != 'held' or not inventory.heldUntil:
        return False
    held_until = _normalize_timestamp(inventory.heldUntil)
    if held_until is None:
        return False
    return held_until <= now


def _clear_hold(inventory: SeatInventory) -> None:
    inventory.status = 'available'
    inventory.heldByUserId = None
    inventory.holdToken = None
    inventory.heldUntil = None


class SeatInventoryGrpcService(SeatInventoryServiceServicer):
    def __init__(self, flask_app=None):
        self.app = flask_app or create_app()

    def HoldSeat(self, request, context):
        """
        Hold a seat for a user with deadlock retry logic.
        Retries up to MAX_DEADLOCK_RETRIES times with exponential backoff.
        """
        last_error = None
        
        for attempt in range(MAX_DEADLOCK_RETRIES):
            try:
                with self.app.app_context():
                    now = datetime.now(UTC)
                    hold_seconds = request.hold_duration_seconds if request.hold_duration_seconds > 0 else 300
                    held_until = now + timedelta(seconds=hold_seconds)
                    hold_token = str(uuid.uuid4())

                    locked_row = (
                        db.session.query(SeatInventory)
                        .filter(SeatInventory.inventoryId == request.inventory_id)
                        .with_for_update()
                        .one_or_none()
                    )

                    if not locked_row:
                        db.session.rollback()
                        return HoldSeatResponse(
                            success=False,
                            status='not_found',
                            held_until='',
                            error_code='INVENTORY_NOT_FOUND',
                            hold_token='',
                        )

                    if _hold_has_expired(locked_row, now):
                        logger.info("Reclaiming expired hold for inventory %s", request.inventory_id)
                        _clear_hold(locked_row)
                        db.session.flush()
                        _delete_hold_cache(request.inventory_id)

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
                                SeatInventory.status: 'held',
                                SeatInventory.heldByUserId: request.user_id,
                                SeatInventory.holdToken: hold_token,
                                SeatInventory.heldUntil: held_until,
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
                    _write_hold_cache(
                        inventory_id=request.inventory_id,
                        user_id=request.user_id,
                        hold_token=hold_token,
                        held_until_iso=held_until.isoformat(),
                        ttl_seconds=hold_seconds,
                    )
                    
                    if attempt > 0:
                        logger.info("HoldSeat succeeded on attempt %d for inventory %s", attempt + 1, request.inventory_id)
                    
                    return HoldSeatResponse(
                        success=True,
                        status='held',
                        held_until=held_until.isoformat(),
                        error_code='',
                        hold_token=hold_token,
                    )
                    
            except sqlalchemy.exc.OperationalError as exc:
                if _is_deadlock_error(exc):
                    if attempt < MAX_DEADLOCK_RETRIES - 1:
                        delay = _calculate_deadlock_delay(attempt)
                        logger.warning(
                            "Deadlock detected for inventory %s (attempt %d/%d). Retrying in %.2fs...",
                            request.inventory_id, attempt + 1, MAX_DEADLOCK_RETRIES, delay
                        )
                        db.session.rollback()
                        time.sleep(delay)
                    else:
                        logger.error(
                            "Deadlock resolution failed for inventory %s after %d attempts",
                            request.inventory_id, MAX_DEADLOCK_RETRIES
                        )
                        db.session.rollback()
                        return HoldSeatResponse(
                            success=False,
                            status='error',
                            held_until='',
                            error_code='DEADLOCK_FAILED',
                            hold_token='',
                        )
                else:
                    # Non-deadlock database error
                    logger.error("Database error in HoldSeat for inventory %s: %s", request.inventory_id, exc)
                    db.session.rollback()
                    return HoldSeatResponse(
                        success=False,
                        status='error',
                        held_until='',
                        error_code='DATABASE_ERROR',
                        hold_token='',
                    )
            except Exception as exc:
                logger.error("Unexpected error in HoldSeat for inventory %s: %s", request.inventory_id, exc)
                db.session.rollback()
                return HoldSeatResponse(
                    success=False,
                    status='error',
                    held_until='',
                    error_code='INTERNAL_ERROR',
                    hold_token='',
                )

    def ReleaseSeat(self, request, context):
        with self.app.app_context():
            # Idempotency check - prevent duplicate release
            idempotency_key = f"release:{request.inventory_id}:{request.hold_token}"
            cached_result = _check_idempotency(idempotency_key)
            if cached_result is not None:
                logger.info("Returning cached release result for inventory %s", request.inventory_id)
                return ReleaseSeatResponse(success=cached_result.get('success', False))
            
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
                result = ReleaseSeatResponse(success=False)
                # Cache the failure result
                _cache_idempotency_result(idempotency_key, {'success': False})
                return result

            inventory.status = 'available'
            inventory.heldByUserId = None
            inventory.holdToken = None
            inventory.heldUntil = None
            db.session.commit()
            _delete_hold_cache(request.inventory_id)
            
            # Cache the success result
            _cache_idempotency_result(idempotency_key, {'success': True})
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

            inventory.status = 'sold'
            inventory.heldByUserId = None
            inventory.holdToken = None
            inventory.heldUntil = None
            db.session.commit()
            _delete_hold_cache(request.inventory_id)
            return SellSeatResponse(success=True)

    def GetSeatStatus(self, request, context):
        with self.app.app_context():
            inventory = db.session.get(SeatInventory, request.inventory_id)
            if not inventory:
                return GetSeatStatusResponse(inventory_id=request.inventory_id, status='not_found', held_until='')

            if _hold_has_expired(inventory, datetime.now(UTC)):
                logger.info("Returning available status for expired hold on inventory %s", request.inventory_id)
                _clear_hold(inventory)
                db.session.commit()
                _delete_hold_cache(request.inventory_id)
                return GetSeatStatusResponse(
                    inventory_id=inventory.inventoryId,
                    status='available',
                    held_until='',
                )

            return GetSeatStatusResponse(
                inventory_id=inventory.inventoryId,
                status=inventory.status,
                held_until=inventory.heldUntil.isoformat() if inventory.heldUntil else '',
            )
