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
from datetime import datetime, timezone

import grpc
import pika
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


def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def _grpc_stub():
    host = os.environ.get("SEAT_INVENTORY_GRPC_HOST", "seat-inventory-service")
    port = os.environ.get("SEAT_INVENTORY_GRPC_PORT", "50051")
    return seat_inventory_pb2_grpc.SeatInventoryServiceStub(
        grpc.insecure_channel(f"{host}:{port}")
    )


def _publish_hold_ttl(inventory_id, user_id, hold_token):
    try:
        conn = pika.BlockingConnection(pika.ConnectionParameters(
            host=os.environ.get("RABBITMQ_HOST", "rabbitmq"),
            port=int(os.environ.get("RABBITMQ_PORT", "5672")),
            credentials=pika.PlainCredentials(
                os.environ.get("RABBITMQ_USER", "guest"),
                os.environ.get("RABBITMQ_PASS", "guest"),
            ),
        ))
        ch = conn.channel()
        ch.basic_publish(
            exchange="",
            routing_key="seat_hold_ttl_queue",
            body=json.dumps({
                "inventoryId": inventory_id,
                "userId": user_id,
                "holdToken": hold_token,
            }),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        conn.close()
    except Exception as exc:
        logger.warning("Failed to publish hold TTL message: %s", exc)


# ── GET /tickets ─────────────────────────────────────────────────────────────

@bp.get("/tickets")
@require_auth
def get_my_tickets():
    user_id = request.user["userId"]
    data, err = call_service("GET", f"{TICKET_SERVICE}/tickets/owner/{user_id}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not fetch tickets.", 503)
    tickets = data.get("tickets", [])

    # Enrich each ticket with event details
    event_cache = {}
    for ticket in tickets:
        event_id = ticket.get("eventId")
        if event_id and event_id not in event_cache:
            event_data, e_err = call_service("GET", f"{EVENT_SERVICE}/events/{event_id}")
            event_cache[event_id] = event_data if not e_err else {}
        if event_id:
            ev = event_cache.get(event_id, {})
            ticket["event"] = {
                "name": ev.get("name"),
                "event_date": ev.get("date") or ev.get("eventDate"),
            }

    return jsonify({"data": tickets}), 200


# ── POST /purchase/hold/<inventory_id> ───────────────────────────────────────

@bp.post("/purchase/hold/<inventory_id>")
@require_auth
def hold_seat(inventory_id):
    user_id = request.user["userId"]

    try:
        stub = _grpc_stub()
        resp = stub.HoldSeat(seat_inventory_pb2.HoldSeatRequest(
            inventory_id=inventory_id,
            user_id=user_id,
            hold_duration_seconds=HOLD_SECONDS,
        ))
    except grpc.RpcError as exc:
        logger.error("gRPC HoldSeat error: %s", exc)
        return _error("SERVICE_UNAVAILABLE", "Seat inventory service unavailable.", 503)

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
    user_id = request.user["userId"]
    body = request.get_json(silent=True) or {}
    hold_token = body.get("holdToken", "")

    try:
        stub = _grpc_stub()
        resp = stub.ReleaseSeat(seat_inventory_pb2.ReleaseSeatRequest(
            inventory_id=inventory_id,
            user_id=user_id,
            hold_token=hold_token,
        ))
    except grpc.RpcError as exc:
        logger.error("gRPC ReleaseSeat error: %s", exc)
        return _error("SERVICE_UNAVAILABLE", "Seat inventory service unavailable.", 503)

    if not resp.success:
        return _error(resp.error_code or "RELEASE_FAILED", "Could not release seat hold.", 409)

    return jsonify({"data": {"inventoryId": inventory_id, "status": "available"}}), 200


# ── POST /purchase/confirm/<inventory_id> ────────────────────────────────────

@bp.post("/purchase/confirm/<inventory_id>")
@require_auth
def confirm_purchase(inventory_id):
    user_id = request.user["userId"]
    body    = request.get_json(silent=True) or {}
    hold_token = body.get("holdToken", "")

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

    # Fetch event (need venueId + price)
    inv_list, err = call_service("GET", f"{SEAT_INV_REST}/inventory/event/{seat_status.inventory_id if hasattr(seat_status, 'inventory_id') else inventory_id}")
    # Fallback: find the inventory record by listing events — we need eventId
    # The seat inventory REST list endpoint returns eventId per record
    # Filter for our inventoryId
    inv_record = None
    if not err:
        inv_record = next(
            (s for s in inv_list.get("inventory", []) if s["inventoryId"] == inventory_id),
            None,
        )

    # If we can't find it that way, the confirm body may supply eventId
    event_id = body.get("eventId") or (inv_record["eventId"] if inv_record else None)
    venue_id = body.get("venueId") or (None)  # resolved from event below

    if not event_id:
        return _error("VALIDATION_ERROR", "Could not resolve eventId for this seat.", 400)

    event_data, err = call_service("GET", f"{EVENT_SERVICE}/events/{event_id}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not fetch event details.", 503)

    venue_id    = event_data.get("venueId")
    ticket_price = float(event_data["price"])

    # 2. Check buyer credits (OutSystems)
    credit_data, err = call_credit_service("GET", f"/credits/{user_id}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not verify credit balance.", 503)

    if credit_data["creditBalance"] < ticket_price:
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
        "creditBalance": credit_data["creditBalance"] - ticket_price,
    })
    if err:
        logger.error("Credit deduction failed for user %s — ticket %s created but credits not deducted", user_id, ticket_id)

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
