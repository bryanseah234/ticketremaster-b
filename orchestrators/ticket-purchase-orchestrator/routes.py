"""
Ticket Purchase Orchestrator routes.

Saga order for confirm:
  1. Validate seat is still held (gRPC GetSeatStatus)
  2. Check credits (OutSystems)
  3. Sell seat (gRPC SellSeat)          COMP: ReleaseSeat
  4. Create ticket record               COMP: (no rollback needed — mark failed and return)
  5. Deduct credits (OutSystems)
  6. Log credit transaction
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

import grpc
import pika
import redis
import seat_inventory_pb2
import seat_inventory_pb2_grpc
from flask import Blueprint, jsonify, request

from middleware import require_auth
from service_client import call_credit_service, call_service

bp     = Blueprint("purchase", __name__)
logger = logging.getLogger(__name__)

TICKET_SERVICE     = os.environ.get("TICKET_SERVICE_URL",             "http://ticket-service:5000")
EVENT_SERVICE      = os.environ.get("EVENT_SERVICE_URL",              "http://event-service:5000")
SEAT_INV_REST      = os.environ.get("SEAT_INVENTORY_SERVICE_URL",     "http://seat-inventory-service:5000")
CREDIT_TXN_SERVICE = os.environ.get("CREDIT_TRANSACTION_SERVICE_URL", "http://credit-transaction-service:5000")

HOLD_SECONDS = int(os.environ.get("SEAT_HOLD_DURATION_SECONDS", "300"))

# Circuit breaker for Redis fallback
REDIS_CB_FAILURE_THRESHOLD = int(os.environ.get("REDIS_CB_FAILURE_THRESHOLD", "3"))
REDIS_CB_RECOVERY_SECONDS = int(os.environ.get("REDIS_CB_RECOVERY_SECONDS", "30"))
_redis_cb_failures = 0
_redis_cb_last_failure_time = 0
_redis_cb_lock = threading.Lock()
_redis_cb_open = False

# gRPC channel pool for resource management
_GRPC_CHANNEL_POOL = []
_GRPC_CHANNEL_LOCK = threading.Lock()
_GRPC_CHANNEL_MAX_SIZE = int(os.environ.get("GRPC_CHANNEL_POOL_SIZE", "5"))
_GRPC_HOST = None  # Track current host to detect config changes


def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def _get_grpc_channel():
    """Get a gRPC channel from the pool or create a new one.
    
    Implements channel pooling to avoid creating new channels on every request.
    Channels are reused across requests and closed on app shutdown.
    """
    global _GRPC_HOST
    
    host = os.environ.get("SEAT_INVENTORY_GRPC_HOST", "seat-inventory-service")
    port = os.environ.get("SEAT_INVENTORY_GRPC_PORT", "50051")
    address = f"{host}:{port}"
    
    # If host changed, close all existing channels and reset
    if _GRPC_HOST is not None and _GRPC_HOST != address:
        logger.info("gRPC host changed from %s to %s, closing all channels", _GRPC_HOST, address)
        with _GRPC_CHANNEL_LOCK:
            for channel in _GRPC_CHANNEL_POOL:
                try:
                    channel.close()
                except Exception:
                    pass
            _GRPC_CHANNEL_POOL.clear()
    
    _GRPC_HOST = address
    
    # Try to get an existing channel from the pool
    with _GRPC_CHANNEL_LOCK:
        if _GRPC_CHANNEL_POOL:
            return _GRPC_CHANNEL_POOL.pop()
    
    # Create a new channel if pool is empty
    logger.debug("Creating new gRPC channel to %s", address)
    return grpc.insecure_channel(address)


def _return_grpc_channel(channel):
    """Return a gRPC channel to the pool for reuse."""
    with _GRPC_CHANNEL_LOCK:
        if len(_GRPC_CHANNEL_POOL) < _GRPC_CHANNEL_MAX_SIZE:
            _GRPC_CHANNEL_POOL.append(channel)
        else:
            # Pool is full, close the channel
            try:
                channel.close()
            except Exception:
                pass


def _grpc_stub():
    """Get a gRPC stub with channel pooling for resource efficiency."""
    channel = _get_grpc_channel()
    return seat_inventory_pb2_grpc.SeatInventoryServiceStub(channel), channel


def _release_grpc_stub(stub_and_channel):
    """Return the gRPC channel to the pool after use."""
    if isinstance(stub_and_channel, tuple) and len(stub_and_channel) == 2:
        _, channel = stub_and_channel
        _return_grpc_channel(channel)


def _get_redis_client():
    """Get Redis client with circuit breaker pattern to prevent cascade failures."""
    global _redis_cb_failures, _redis_cb_last_failure_time, _redis_cb_open
    
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return None
    
    # Check if circuit breaker is open
    with _redis_cb_lock:
        if _redis_cb_open:
            # Check if recovery period has passed
            if time.time() - _redis_cb_last_failure_time > REDIS_CB_RECOVERY_SECONDS:
                logger.info("Redis circuit breaker entering half-open state, allowing retry")
                _redis_cb_open = False
                _redis_cb_failures = 0
            else:
                logger.warning("Redis circuit breaker is open - skipping Redis call")
                return None
    
    try:
        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        
        # Reset circuit breaker on success
        with _redis_cb_lock:
            if _redis_cb_failures > 0:
                logger.info("Redis circuit breaker reset after successful connection")
                _redis_cb_failures = 0
                _redis_cb_open = False
        
        return client
    except Exception as exc:
        logger.warning("Redis unavailable during purchase confirmation: %s", exc)
        
        # Update circuit breaker state
        with _redis_cb_lock:
            _redis_cb_failures += 1
            _redis_cb_last_failure_time = time.time()
            if _redis_cb_failures >= REDIS_CB_FAILURE_THRESHOLD:
                _redis_cb_open = True
                logger.warning("Redis circuit breaker triggered after %d consecutive failures", _redis_cb_failures)
        
        return None


def _get_cached_hold(inventory_id):
    client = _get_redis_client()
    if client is None:
        return None
    try:
        cached_hold = client.get(f"hold:{inventory_id}")
    except Exception as exc:
        logger.warning("Redis hold cache read failed for %s: %s", inventory_id, exc)
        return None
    if not cached_hold:
        logger.info("Purchase confirm cache miss for %s", inventory_id)
        return None
    try:
        payload = json.loads(cached_hold)
    except json.JSONDecodeError:
        logger.warning("Redis hold cache payload invalid for %s", inventory_id)
        return None
    logger.info("Purchase confirm cache hit for %s", inventory_id)
    return payload


def _parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _validate_hold_state(status, held_until):
    if status != "held":
        code = "PAYMENT_HOLD_EXPIRED" if status == "available" else "SEAT_UNAVAILABLE"
        return _error(code, "Seat is no longer held. Please re-select.", 410 if code == "PAYMENT_HOLD_EXPIRED" else 409)
    held_until_at = _parse_timestamp(held_until)
    if held_until and held_until_at is None:
        return None
    if held_until_at and datetime.now(timezone.utc) > held_until_at:
        return _error("PAYMENT_HOLD_EXPIRED", "Seat hold has expired. Please re-select.", 410)
    return None


def _publish_hold_ttl(inventory_id, user_id, hold_token):
    """Publish hold TTL message to RabbitMQ with retry and exponential backoff."""
    MAX_RETRIES = 3
    BACKOFF_DELAYS = [1, 2, 4]  # seconds
    
    message = json.dumps({
        "inventoryId": inventory_id,
        "userId": user_id,
        "holdToken": hold_token,
    })
    
    for attempt in range(MAX_RETRIES):
        try:
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
                routing_key="seat_hold_ttl_queue",
                body=message,
                properties=pika.BasicProperties(delivery_mode=2),
            )
            conn.close()
            if attempt > 0:
                logger.info("RabbitMQ publish succeeded on attempt %d", attempt + 1)
            return
        except Exception as exc:
            if attempt < MAX_RETRIES - 1:
                delay = BACKOFF_DELAYS[attempt]
                logger.warning("RabbitMQ publish failed (attempt %d/%d): %s. Retrying in %ds...", 
                             attempt + 1, MAX_RETRIES, exc, delay)
                time.sleep(delay)
            else:
                logger.error("RabbitMQ publish failed after %d attempts: %s", MAX_RETRIES, exc)


# ── POST /purchase/hold/<inventory_id> ───────────────────────────────────────

@bp.post("/purchase/hold/<inventory_id>")
@require_auth
def hold_seat(inventory_id):
    """
    Hold a seat for purchase — reserves for SEAT_HOLD_DURATION_SECONDS
    ---
    tags:
      - Purchase
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: inventory_id
        required: true
        type: string
        example: inv_001
    responses:
      200:
        description: Seat held — returns holdToken and heldUntil timestamp
      401:
        description: Unauthorized
      404:
        description: Seat not found
      409:
        description: Seat already held or sold
      503:
        description: Seat inventory service unavailable
    """
    user_id = request.user["userId"]

    stub = None
    channel = None
    try:
        stub, channel = _grpc_stub()
        resp = stub.HoldSeat(seat_inventory_pb2.HoldSeatRequest(
            inventory_id=inventory_id,
            user_id=user_id,
            hold_duration_seconds=HOLD_SECONDS,
        ))
    except grpc.RpcError as exc:
        logger.error("gRPC HoldSeat error: %s", exc)
        return _error("SERVICE_UNAVAILABLE", "Seat inventory service unavailable.", 503)
    finally:
        if stub is not None:
            _release_grpc_stub((stub, channel))

    if not resp.success:
        code   = resp.error_code or "SEAT_UNAVAILABLE"
        status = 404 if code == "INVENTORY_NOT_FOUND" else 409
        return _error(code, "Seat could not be held.", status)

    _publish_hold_ttl(inventory_id, user_id, resp.hold_token)

    return jsonify({"data": {
        "inventoryId": inventory_id,
        "status":      "held",
        "heldUntil":   resp.held_until,
        "holdToken":   resp.hold_token,
    }}), 200


# ── DELETE /purchase/hold/<inventory_id> ─────────────────────────────────────

@bp.delete("/purchase/hold/<inventory_id>")
@require_auth
def release_hold(inventory_id):
    """
    Manually release a seat hold before it expires
    ---
    tags:
      - Purchase
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: inventory_id
        required: true
        type: string
        example: inv_001
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [holdToken]
          properties:
            holdToken:
              type: string
              example: c378f45d-4236-4d49-8d93-d5e965964ada
              description: The holdToken returned from POST /purchase/hold/<inventory_id>
    responses:
      200:
        description: Seat released — status back to available
        schema:
          type: object
          properties:
            data:
              type: object
              properties:
                inventoryId:
                  type: string
                  example: inv_001
                status:
                  type: string
                  example: available
      401:
        description: Unauthorized
      409:
        description: Could not release — hold token mismatch or seat not held
      503:
        description: Seat inventory service unavailable
    """
    user_id = request.user["userId"]
    body = request.get_json(silent=True) or {}
    hold_token = body.get("holdToken", "")

    stub = None
    channel = None
    try:
        stub, channel = _grpc_stub()
        resp = stub.ReleaseSeat(seat_inventory_pb2.ReleaseSeatRequest(
            inventory_id=inventory_id,
            user_id=user_id,
            hold_token=hold_token,
        ))
    except grpc.RpcError as exc:
        logger.error("gRPC ReleaseSeat error: %s", exc)
        return _error("SERVICE_UNAVAILABLE", "Seat inventory service unavailable.", 503)
    finally:
        if stub is not None:
            _release_grpc_stub((stub, channel))

    if not resp.success:
        return _error(resp.error_code or "RELEASE_FAILED", "Could not release seat hold.", 409)

    return jsonify({"data": {"inventoryId": inventory_id, "status": "available"}}), 200


# ── POST /purchase/confirm/<inventory_id> ────────────────────────────────────

@bp.post("/purchase/confirm/<inventory_id>")
@require_auth
def confirm_purchase(inventory_id):
    """
    Confirm a seat purchase — deducts credits and creates ticket
    ---
    tags:
      - Purchase
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: inventory_id
        required: true
        type: string
        example: inv_001
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [eventId, holdToken]
          properties:
            eventId:
              type: string
              example: evt_001
            holdToken:
              type: string
              example: c378f45d-4236-4d49-8d93-d5e965964ada
    responses:
      201:
        description: Ticket created successfully
      400:
        description: Missing eventId or validation error
      402:
        description: Insufficient credits
      409:
        description: Seat no longer available
      410:
        description: Seat hold has expired
      500:
        description: Ticket creation failed
    """
    user_id = request.user["userId"]
    body = request.get_json(silent=True) or {}
    event_id = body.get("eventId")
    hold_token = body.get("holdToken", "")

    if not event_id:
        return _error("VALIDATION_ERROR", "eventId is required.", 400)

    # Get gRPC stub with channel pooling
    stub = None
    channel = None
    try:
        stub, channel = _grpc_stub()
        cached_hold = _get_cached_hold(inventory_id)
        if isinstance(cached_hold, dict):
            cached_user_id = cached_hold.get("heldByUserId")
            cached_hold_token = cached_hold.get("holdToken")
            if cached_user_id and cached_user_id != user_id:
                return _error("SEAT_UNAVAILABLE", "Seat is no longer held. Please re-select.", 409)
            if hold_token and cached_hold_token and cached_hold_token != hold_token:
                return _error("SEAT_UNAVAILABLE", "Seat is no longer held. Please re-select.", 409)
            validation_error = _validate_hold_state(
                status=str(cached_hold.get("status", "")),
                held_until=str(cached_hold.get("heldUntil", "")),
            )
            if validation_error:
                return validation_error
            logger.info("Purchase confirm using Redis hold cache for %s", inventory_id)
        else:
            try:
                seat_status = stub.GetSeatStatus(
                    seat_inventory_pb2.GetSeatStatusRequest(inventory_id=inventory_id)
                )
            except grpc.RpcError as exc:
                logger.error("gRPC GetSeatStatus error: %s", exc)
                return _error("SERVICE_UNAVAILABLE", "Seat inventory service unavailable.", 503)
            validation_error = _validate_hold_state(
                status=seat_status.status,
                held_until=seat_status.held_until,
            )
            if validation_error:
                return validation_error
            logger.info("Purchase confirm falling back to gRPC status for %s", inventory_id)

        event_data, err = call_service("GET", f"{EVENT_SERVICE}/events/{event_id}")
        if err:
            return _error("SERVICE_UNAVAILABLE", "Could not fetch event details.", 503)

        venue_id     = event_data.get("venueId")
        ticket_price = float(event_data["price"])

        # 2. Check buyer credits (OutSystems)
        credit_data, err = call_credit_service("GET", f"/credits/{user_id}")
        if err:
            return _error("SERVICE_UNAVAILABLE", "Could not verify credit balance.", 503)

        logger.info("Credit data response: %s", credit_data)

        # Handle different possible field names from OutSystems
        # and treat missing/zero balance as 0.0
        raw_balance = (
            credit_data.get("creditBalance")
            if credit_data.get("creditBalance") is not None
            else credit_data.get("CreditBalance")
            if credit_data.get("CreditBalance") is not None
            else credit_data.get("balance")
            if credit_data.get("balance") is not None
            else 0.0
        )
        balance = float(raw_balance)

        if balance < ticket_price:
            return _error("INSUFFICIENT_CREDITS", "Insufficient credits for this purchase.", 402)

        # 3. Sell seat via gRPC
        try:
            sell_resp = stub.SellSeat(seat_inventory_pb2.SellSeatRequest(
                inventory_id=inventory_id,
                user_id=user_id,
                hold_token=hold_token,
            ))
            if not sell_resp.success:
                return _error("SEAT_UNAVAILABLE", "Could not confirm seat as sold.", 409)
        except grpc.RpcError as exc:
            logger.error("gRPC SellSeat error: %s", exc)
            return _error("SERVICE_UNAVAILABLE", "Seat inventory service unavailable.", 503)

        # 4. Create ticket record
        ticket_data, err = call_service("POST", f"{TICKET_SERVICE}/tickets", json={
            "inventoryId": inventory_id,
            "ownerId":     user_id,
            "venueId":     venue_id,
            "eventId":     event_id,
            "price":       ticket_price,
            "status":      "active",
        })
        if err:
            # Compensate: release seat back
            try:
                stub.ReleaseSeat(seat_inventory_pb2.ReleaseSeatRequest(
                    inventory_id=inventory_id,
                    user_id=user_id,
                    hold_token=hold_token,
                ))
            except Exception:
                pass
            return _error("INTERNAL_ERROR", "Could not create ticket record.", 500)

        ticket_id = ticket_data["ticketId"]

        # 5. Deduct credits (OutSystems)
        _, err = call_credit_service("PATCH", f"/credits/{user_id}", json={
            "creditBalance": balance - ticket_price,
        })
        if err:
            # Compensating action: mark ticket as payment_failed and release seat
            logger.error("Credit deduction failed for user %s — ticket %s created but credits not deducted", user_id, ticket_id)
            compensation_errors = []
            
            try:
                # Mark ticket as payment_failed for manual reconciliation
                _, patch_err = call_service("PATCH", f"{TICKET_SERVICE}/tickets/{ticket_id}", json={
                    "status": "payment_failed",
                })
                if patch_err:
                    compensation_errors.append(f"Failed to mark ticket status: {patch_err}")
                    logger.error("Failed to mark ticket %s as payment_failed: %s", ticket_id, patch_err)
            except Exception as patch_err:
                compensation_errors.append(f"Exception marking ticket status: {str(patch_err)}")
                logger.error("Failed to mark ticket %s as payment_failed: %s", ticket_id, patch_err)
            
            try:
                # Release the seat back to available
                stub.ReleaseSeat(seat_inventory_pb2.ReleaseSeatRequest(
                    inventory_id=inventory_id,
                    user_id=user_id,
                    hold_token=hold_token,
                ))
            except Exception as release_err:
                compensation_errors.append(f"Failed to release seat: {str(release_err)}")
                logger.error("Failed to release seat %s after credit deduction failure: %s", inventory_id, release_err)
            
            # Log compensation failures to DLQ for manual intervention
            if compensation_errors:
                logger.error(
                    "Compensation incomplete for purchase failure. Ticket: %s, Errors: %s",
                    ticket_id,
                    "; ".join(compensation_errors)
                )
                # Send to DLQ for manual reconciliation
                try:
                    import pika
                    import json as json_module
                    from datetime import UTC
                    
                    message = json_module.dumps({
                        "event": "purchase_compensation_failed",
                        "ticket_id": ticket_id,
                        "inventory_id": inventory_id,
                        "user_id": user_id,
                        "errors": compensation_errors,
                        "timestamp": datetime.now(UTC).isoformat(),
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
                        routing_key="purchase_compensation_dlq",
                        body=message,
                        properties=pika.BasicProperties(delivery_mode=2),
                    )
                    conn.close()
                    logger.info("Purchase compensation failure logged to DLQ for ticket %s", ticket_id)
                except Exception as dlq_err:
                    logger.error("Failed to log compensation failure to DLQ: %s", dlq_err)
            
            return _error("CREDIT_DEDUCTION_FAILED", "Ticket created but credit deduction failed. Please contact support.", 500)

        # 6. Log credit transaction
        call_service("POST", f"{CREDIT_TXN_SERVICE}/credit-transactions", json={
            "userId":      user_id,
            "delta":       -ticket_price,
            "reason":      "ticket_purchase",
            "referenceId": ticket_id,
        })

        return jsonify({"data": {
            "ticketId":    ticket_id,
            "eventId":     event_id,
            "venueId":     venue_id,
            "inventoryId": inventory_id,
            "price":       ticket_price,
            "status":      "active",
            "createdAt":   ticket_data.get("createdAt"),
        }}), 201
    finally:
        if stub is not None:
            _release_grpc_stub((stub, channel))
