"""
Transfer Orchestrator routes.

P2P transfer flow:
  POST /transfer/initiate            buyer initiates
  POST /transfer/<id>/buyer-verify   buyer submits OTP → seller OTP sent
  POST /transfer/<id>/seller-verify  seller submits OTP → saga executes
  POST /transfer/<id>/seller-accept  legacy seller acceptance → seller OTP sent
  GET  /transfer/<id>                poll status (buyer or seller)
  POST /transfer/<id>/cancel         cancel in-progress transfer

Saga on seller-verify:
  1. Deduct buyer credits (OutSystems)     COMP: restore buyer
  2. Credit seller (OutSystems)            COMP: restore buyer + seller
  3. Log buyer credit txn
  4. Log seller credit txn
  5. Transfer ticket ownership
  6. Mark listing completed
  7. Mark transfer completed
"""
import json
import logging
import os
import time
from datetime import datetime, timezone

import pika
from flask import Blueprint, jsonify, request

from middleware import require_auth
from service_client import call_credit_service, call_service

bp     = Blueprint("transfer", __name__)
logger = logging.getLogger(__name__)

MARKETPLACE_SERVICE = os.environ.get("MARKETPLACE_SERVICE_URL",        "http://marketplace-service:5000")
TRANSFER_SERVICE    = os.environ.get("TRANSFER_SERVICE_URL",           "http://transfer-service:5000")
OTP_WRAPPER         = os.environ.get("OTP_WRAPPER_URL",                "http://otp-wrapper:5000")
CREDIT_TXN_SERVICE  = os.environ.get("CREDIT_TRANSACTION_SERVICE_URL", "http://credit-transaction-service:5000")
TICKET_SERVICE      = os.environ.get("TICKET_SERVICE_URL",             "http://ticket-service:5000")
USER_SERVICE        = os.environ.get("USER_SERVICE_URL",               "http://user-service:5000")
EVENT_SERVICE       = os.environ.get("EVENT_SERVICE_URL",              "http://event-service:5000")
VENUE_SERVICE       = os.environ.get("VENUE_SERVICE_URL",              "http://venue-service:5000")
SEAT_INV_SERVICE    = os.environ.get("SEAT_INVENTORY_SERVICE_URL",     "http://seat-inventory-service:5000")
SEAT_SERVICE        = os.environ.get("SEAT_SERVICE_URL",               "http://seat-service:5000")
NOTIFICATION_SERVICE = os.environ.get("NOTIFICATION_SERVICE_URL",      "http://notification-service:8109")


def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def _get_credit_balance(credit_data):
    """Safely extract credit balance from OutSystems response regardless of field name."""
    raw = (
        credit_data.get("creditBalance")
        if credit_data.get("creditBalance") is not None
        else credit_data.get("CreditBalance")
        if credit_data.get("CreditBalance") is not None
        else credit_data.get("balance")
        if credit_data.get("balance") is not None
        else 0.0
    )
    return float(raw)


def _safe_get(url, **kwargs):
    """Return service data or None without failing the caller."""
    data, err = call_service("GET", url, **kwargs)
    if err:
        logger.warning("Downstream enrichment lookup failed for %s: %s", url, err)
        return None
    return data


def _first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _build_transfer_context(transfer):
    """Load related transfer resources while tolerating partial failures."""
    listing = _safe_get(f"{MARKETPLACE_SERVICE}/listings/{transfer['listingId']}") if transfer.get("listingId") else None

    ticket_id = _first_present(
        transfer.get("ticketId"),
        (listing or {}).get("ticketId"),
    )
    ticket = _safe_get(f"{TICKET_SERVICE}/tickets/{ticket_id}") if ticket_id else None

    event_id = _first_present(
        transfer.get("eventId"),
        (ticket or {}).get("eventId"),
    )
    event = _safe_get(f"{EVENT_SERVICE}/events/{event_id}") if event_id else None

    venue_id = _first_present(
        (event or {}).get("venueId"),
        (ticket or {}).get("venueId"),
        transfer.get("venueId"),
    )
    venue = _safe_get(f"{VENUE_SERVICE}/venues/{venue_id}") if venue_id else None

    seller = _safe_get(f"{USER_SERVICE}/users/{transfer['sellerId']}") if transfer.get("sellerId") else None
    buyer = _safe_get(f"{USER_SERVICE}/users/{transfer['buyerId']}") if transfer.get("buyerId") else None

    seat = None
    inventory_id = _first_present(
        (ticket or {}).get("inventoryId"),
        transfer.get("inventoryId"),
    )
    if event_id and inventory_id:
        inv_data = _safe_get(f"{SEAT_INV_SERVICE}/inventory/event/{event_id}")
        inventory_item = next(
            (
                item
                for item in (inv_data or {}).get("inventory", [])
                if item.get("inventoryId") == inventory_id
            ),
            None,
        )
        seat_id = (inventory_item or {}).get("seatId")
        if venue_id and seat_id:
            seats_data = _safe_get(f"{SEAT_SERVICE}/seats/venue/{venue_id}")
            seat = next(
                (
                    item
                    for item in (seats_data or {}).get("seats", [])
                    if item.get("seatId") == seat_id
                ),
                None,
            )

    return {
        "buyer": buyer,
        "seller": seller,
        "listing": listing,
        "ticket": ticket,
        "ticketId": ticket_id,
        "event": event,
        "eventId": event_id,
        "venue": venue,
        "seat": seat,
    }


def _build_event_payload(context):
    event = context["event"] or {}
    venue = context["venue"]
    event_id = _first_present(event.get("eventId"), context["eventId"])

    if not any((event_id, event.get("name"), event.get("date"), venue)):
        return None

    return {
        "id": event_id,
        "eventId": event_id,
        "name": event.get("name"),
        "date": event.get("date"),
        "image": _first_present(event.get("image"), event.get("imageUrl")),
        "venue": venue,
    }


def _build_seat_payload(context):
    seat = context["seat"] or {}
    row_number = _first_present(seat.get("rowNumber"), seat.get("row"))
    seat_number = _first_present(seat.get("seatNumber"), seat.get("seat"))
    gate = _first_present(seat.get("gate"), seat.get("entryGate"))
    section = seat.get("section")

    if not any((seat.get("seatId"), row_number, seat_number, gate, section)):
        return None

    return {
        "seatId": seat.get("seatId"),
        "section": section,
        "row": row_number,
        "rowNumber": row_number,
        "seat": seat_number,
        "seatNumber": seat_number,
        "gate": gate,
    }


def _build_transfer_notification_payload(event_type, transfer_data):
    enriched = _enrich_transfer(transfer_data)
    payload = {
        "eventType": event_type,
        "transferId": enriched.get("transferId"),
        "listingId": enriched.get("listingId"),
        "ticketId": enriched.get("ticketId"),
        "buyerId": enriched.get("buyerId"),
        "buyerName": enriched.get("buyerName"),
        "sellerId": enriched.get("sellerId"),
        "sellerName": enriched.get("sellerName"),
        "status": enriched.get("status"),
        "creditAmount": enriched.get("creditAmount"),
        "completedAt": enriched.get("completedAt"),
        "event": enriched.get("event"),
        "seat": enriched.get("seat"),
    }
    if payload["event"]:
        payload["eventName"] = payload["event"].get("name")
    return {key: value for key, value in payload.items() if value is not None}


def _load_enriched_transfer(transfer_id, fallback=None):
    """Reload the latest transfer state and enrich it for UI responses."""
    transfer, err = call_service("GET", f"{TRANSFER_SERVICE}/transfers/{transfer_id}")
    if err:
        logger.warning("Failed to reload transfer %s after update: %s", transfer_id, err)
        return _enrich_transfer(fallback) if fallback else None
    return _enrich_transfer(transfer)


def _broadcast_notification(notification_type, payload):
    """Broadcast notification payload without breaking the transfer flow."""
    try:
        _, err = call_service("POST", f"{NOTIFICATION_SERVICE}/broadcast", json={
            "type": notification_type,
            "payload": payload,
        })
        if err:
            logger.warning("Failed to broadcast %s notification: %s", notification_type, err)
            return
        logger.info(
            "Broadcasted %s notification for transfer %s",
            notification_type,
            payload.get("transferId"),
        )
    except Exception as exc:
        logger.warning("Failed to broadcast %s notification: %s", notification_type, exc)


def _broadcast_transfer_notification(event_type, transfer_data):
    """
    Broadcast transfer state change to notification service.
    Non-blocking — failures are logged but do not affect transfer flow.
    """
    payload = _build_transfer_notification_payload(event_type, transfer_data)
    _broadcast_notification("transfer_update", payload)


def _publish_seller_notification(transfer_id, seller_id):
    """Publish seller notification to RabbitMQ with retry and exponential backoff."""
    MAX_RETRIES = 3
    BACKOFF_DELAYS = [1, 2, 4]  # seconds
    
    message = json.dumps({"transferId": transfer_id, "sellerId": seller_id})
    
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
                routing_key="seller_notification_queue",
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


def _publish_transfer_timeout(transfer_id, listing_id, buyer_id, seller_id):
    """Publish transfer timeout message to RabbitMQ with 24-hour TTL."""
    MAX_RETRIES = 3
    BACKOFF_DELAYS = [1, 2, 4]  # seconds
    
    timeout_ms = int(os.environ.get("TRANSFER_TIMEOUT_HOURS", "24")) * 3600 * 1000
    
    message = json.dumps({
        "transferId": transfer_id,
        "listingId": listing_id,
        "buyerId": buyer_id,
        "sellerId": seller_id,
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
            
            # Declare queue with TTL support
            ch.queue_declare(
                queue="transfer_timeout_queue",
                durable=True,
                arguments={"x-message-ttl": timeout_ms},
            )
            
            ch.basic_publish(
                exchange="",
                routing_key="transfer_timeout_queue",
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    expiration=str(timeout_ms),
                ),
            )
            conn.close()
            logger.info("Published transfer timeout message for %s", transfer_id)
            if attempt > 0:
                logger.info("RabbitMQ timeout publish succeeded on attempt %d", attempt + 1)
            return
        except Exception as exc:
            if attempt < MAX_RETRIES - 1:
                delay = BACKOFF_DELAYS[attempt]
                logger.warning("RabbitMQ timeout publish failed (attempt %d/%d): %s. Retrying in %ds...", 
                             attempt + 1, MAX_RETRIES, exc, delay)
                time.sleep(delay)
            else:
                logger.error("RabbitMQ timeout publish failed after %d attempts: %s", MAX_RETRIES, exc)


def _execute_saga(transfer_id, buyer_id, seller_id, credit_amount, ticket_id, listing_id,
                  buyer_balance, seller_balance):
    completed = []
    compensation_errors = []
    try:
        # 1. Deduct buyer
        _, err = call_credit_service("PATCH", f"/credits/{buyer_id}",
                            json={"creditBalance": buyer_balance - credit_amount})
        if err:
            raise RuntimeError(f"Credit deduction for buyer failed: {err}")
        completed.append("buyer_deducted")

        # 2. Credit seller
        _, err = call_credit_service("PATCH", f"/credits/{seller_id}",
                            json={"creditBalance": seller_balance + credit_amount})
        if err:
            raise RuntimeError(f"Credit addition for seller failed: {err}")
        completed.append("seller_credited")

        # 3. Log buyer txn
        _, err = call_service("POST", f"{CREDIT_TXN_SERVICE}/credit-transactions", json={
            "userId": buyer_id, "delta": -credit_amount,
            "reason": "p2p_sent", "referenceId": transfer_id,
        })
        if err:
            raise RuntimeError(f"Buyer transaction log failed: {err}")
        completed.append("buyer_txn_logged")

        # 4. Log seller txn
        _, err = call_service("POST", f"{CREDIT_TXN_SERVICE}/credit-transactions", json={
            "userId": seller_id, "delta": credit_amount,
            "reason": "p2p_received", "referenceId": transfer_id,
        })
        if err:
            raise RuntimeError(f"Seller transaction log failed: {err}")
        completed.append("seller_txn_logged")

        # 5. Transfer ticket
        _, err = call_service("PATCH", f"{TICKET_SERVICE}/tickets/{ticket_id}", json={
            "ownerId": buyer_id, "status": "active",
        })
        if err:
            raise RuntimeError(f"Ticket transfer failed: {err}")
        completed.append("ticket_transferred")

        # 6. Complete listing
        _, err = call_service("PATCH", f"{MARKETPLACE_SERVICE}/listings/{listing_id}", json={"status": "completed"})
        if err:
            raise RuntimeError(f"Listing completion failed: {err}")
        completed.append("listing_completed")

        # 7. Complete transfer
        _, err = call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={
            "status": "completed",
            "completedAt": datetime.now(timezone.utc).isoformat(),
        })
        if err:
            raise RuntimeError(f"Transfer record completion failed: {err}")
        completed.append("transfer_completed")

    except Exception as exc:
        logger.error("Saga failed at step %d (%s completed): %s", len(completed), ", ".join(completed), exc)
        
        # Reverse compensation in reverse order
        try:
            if "listing_completed" in completed:
                _, err = call_service("PATCH", f"{MARKETPLACE_SERVICE}/listings/{listing_id}",
                                     json={"status": "active"})
                if err:
                    compensation_errors.append(f"Failed to revert listing status: {err}")
                    logger.error("Failed to revert listing %s status: %s", listing_id, err)

            if "ticket_transferred" in completed:
                _, err = call_service("PATCH", f"{TICKET_SERVICE}/tickets/{ticket_id}",
                                     json={"ownerId": seller_id, "status": "sold"})
                if err:
                    compensation_errors.append(f"Failed to revert ticket ownership: {err}")
                    logger.error("Failed to revert ticket %s ownership: %s", ticket_id, err)

            if "seller_credited" in completed:
                _, err = call_credit_service("PATCH", f"/credits/{seller_id}",
                                            json={"creditBalance": seller_balance})
                if err:
                    compensation_errors.append(f"Failed to restore seller balance: {err}")
                    logger.error("Failed to restore seller %s balance: %s", seller_id, err)
            
            if "buyer_deducted" in completed:
                _, err = call_credit_service("PATCH", f"/credits/{buyer_id}",
                                            json={"creditBalance": buyer_balance})
                if err:
                    compensation_errors.append(f"Failed to restore buyer balance: {err}")
                    logger.error("Failed to restore buyer %s balance: {err}", buyer_id, err)
            
            # Reverse transaction logs if they were created
            if "seller_txn_logged" in completed:
                # Mark seller transaction as reversed
                _, err = call_service("PATCH", f"{CREDIT_TXN_SERVICE}/credit-transactions/reference/{transfer_id}",
                                     json={"status": "reversed", "reason": "transfer_failed"})
                if err:
                    compensation_errors.append(f"Failed to reverse seller transaction log: {err}")
                    logger.error("Failed to reverse seller transaction log: %s", err)
            
            if "buyer_txn_logged" in completed:
                # Mark buyer transaction as reversed
                _, err = call_service("PATCH", f"{CREDIT_TXN_SERVICE}/credit-transactions/reference/{transfer_id}",
                                     json={"status": "reversed", "reason": "transfer_failed"})
                if err:
                    compensation_errors.append(f"Failed to reverse buyer transaction log: {err}")
                    logger.error("Failed to reverse buyer transaction log: %s", err)
        except Exception as comp_err:
            compensation_errors.append(f"Compensation exception: {str(comp_err)}")
            logger.error("Exception during compensation: %s", comp_err)
        
        # Mark transfer as failed
        call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={"status": "failed"})
        
        # Log compensation failures to DLQ for manual intervention
        if compensation_errors:
            logger.error(
                "Transfer saga compensation incomplete. Transfer: %s, Errors: %s",
                transfer_id,
                "; ".join(compensation_errors)
            )
            # Send to DLQ for manual reconciliation
            try:
                import pika
                import json as json_module
                from datetime import UTC
                
                message = json_module.dumps({
                    "event": "transfer_compensation_failed",
                    "transfer_id": transfer_id,
                    "buyer_id": buyer_id,
                    "seller_id": seller_id,
                    "completed_steps": completed,
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
                    routing_key="transfer_compensation_dlq",
                    body=message,
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                conn.close()
                logger.info("Transfer compensation failure logged to DLQ for transfer %s", transfer_id)
            except Exception as dlq_err:
                logger.error("Failed to log compensation failure to DLQ: %s", dlq_err)
        
        raise exc


# ── POST /transfer/initiate ───────────────────────────────────────────────────

@bp.post("/transfer/initiate")
@require_auth
def initiate():
    """
    Initiate a P2P ticket transfer as the buyer
    ---
    tags:
      - Transfer
    security:
      - BearerAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [listingId]
          properties:
            listingId:
              type: string
              example: lst_001
    responses:
      201:
        description: Transfer created — status pending_buyer_otp
      400:
        description: Listing not active
      401:
        description: Unauthorized
      402:
        description: Insufficient credits
      403:
        description: Cannot buy your own listing
      404:
        description: Listing not found
    """
    buyer_id = request.user["userId"]
    body     = request.get_json(silent=True) or {}

    if not body.get("listingId"):
        return _error("VALIDATION_ERROR", "listingId is required.", 400)

    listing, err = call_service("GET", f"{MARKETPLACE_SERVICE}/listings/{body['listingId']}")
    if err == "LISTING_NOT_FOUND":
        return _error("LISTING_NOT_FOUND", "Listing not found.", 404)
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve listing.", 503)

    if listing["status"] != "active":
        return _error("LISTING_NOT_FOUND", "Listing is no longer available.", 400)

    seller_id = listing["sellerId"]
    if seller_id == buyer_id:
        return _error("AUTH_FORBIDDEN", "You cannot purchase your own listing.", 403)

    credit_amount = listing["price"]

    # Check buyer has sufficient credits
    credit_data, err = call_credit_service("GET", f"/credits/{buyer_id}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not verify balance.", 503)

    buyer_balance = _get_credit_balance(credit_data)
    if buyer_balance < credit_amount:
        return _error("INSUFFICIENT_CREDITS", "Please top up your balance to buy this ticket.", 402)

    transfer, err = call_service("POST", f"{TRANSFER_SERVICE}/transfers", json={
        "listingId":    body["listingId"],
        "buyerId":      buyer_id,
        "sellerId":     seller_id,
        "creditAmount": credit_amount,
    })
    if err:
        return _error("INTERNAL_ERROR", "Could not create transfer record.", 500)

    buyer, err = call_service("GET", f"{USER_SERVICE}/users/{buyer_id}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve buyer details.", 503)

    buyer_otp, err = call_service("POST", f"{OTP_WRAPPER}/otp/send",
                                  json={"phoneNumber": buyer["phoneNumber"]})
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not send OTP to buyer.", 503)

    call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer['transferId']}", json={
        "buyerVerificationSid": buyer_otp["sid"],
        "status":               "pending_buyer_otp",
    })
    
    # Schedule timeout for auto-cancellation
    _publish_transfer_timeout(
        transfer["transferId"],
        body["listingId"],
        buyer_id,
        seller_id,
    )
    
    # Broadcast transfer initiation
    _broadcast_transfer_notification("transfer_initiated", {
        "transferId": transfer["transferId"],
        "buyerId": buyer_id,
        "sellerId": seller_id,
        "status": "pending_buyer_otp",
    })

    initiated_transfer = _enrich_transfer({
        **transfer,
        "listingId": body["listingId"],
        "buyerId": buyer_id,
        "sellerId": seller_id,
        "creditAmount": credit_amount,
        "buyerVerificationSid": buyer_otp["sid"],
        "status": "pending_buyer_otp",
    })

    return jsonify({"data": {
        **initiated_transfer,
        "transferId": transfer["transferId"],
        "status": "pending_buyer_otp",
        "message": "Buyer OTP sent. Verify your identity to continue the transfer.",
    }}), 201


# ── POST /transfer/<id>/buyer-verify ─────────────────────────────────────────

@bp.post("/transfer/<transfer_id>/buyer-verify")
@require_auth
def buyer_verify(transfer_id):
    """
    Buyer submits OTP to verify their identity
    ---
    tags:
      - Transfer
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: transfer_id
        required: true
        type: string
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [otp]
          properties:
            otp:
              type: string
              example: "123456"
    responses:
      200:
        description: Buyer verified — seller OTP sent and seller notified
      400:
        description: Invalid OTP or wrong transfer status
      401:
        description: Unauthorized
      403:
        description: Access denied
    """
    buyer_id = request.user["userId"]
    body     = request.get_json(silent=True) or {}

    if not body.get("otp"):
        return _error("VALIDATION_ERROR", "otp is required.", 400)

    transfer, err = call_service("GET", f"{TRANSFER_SERVICE}/transfers/{transfer_id}")
    if err:
        return _error("TRANSFER_NOT_FOUND", "Transfer not found.", 404)
    if transfer["buyerId"] != buyer_id:
        return _error("AUTH_FORBIDDEN", "Access denied.", 403)
    if (
        transfer["status"] != "pending_buyer_otp"
        or transfer.get("buyerOtpVerified")
        or not transfer.get("buyerVerificationSid")
    ):
        return _error("VALIDATION_ERROR", "Transfer is not awaiting buyer OTP.", 400)

    buyer, err = call_service("GET", f"{USER_SERVICE}/users/{transfer['buyerId']}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve buyer details.", 503)

    verify, err = call_service("POST", f"{OTP_WRAPPER}/otp/verify", json={
        "sid": transfer["buyerVerificationSid"],
        "otp": body["otp"],
        "phoneNumber": buyer["phoneNumber"],
    })
    if err or not verify.get("verified"):
        return _error("VALIDATION_ERROR", "OTP is incorrect or has expired.", 400)

    call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={
        "buyerOtpVerified": True,
    })

    seller_id = transfer["sellerId"]
    seller, err = call_service("GET", f"{USER_SERVICE}/users/{seller_id}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve seller details.", 503)

    seller_otp, err = call_service("POST", f"{OTP_WRAPPER}/otp/send",
                                   json={"phoneNumber": seller["phoneNumber"]})
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not send OTP to seller.", 503)

    call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={
        "buyerOtpVerified":     True,
        "sellerVerificationSid": seller_otp["sid"],
        "status":               "pending_seller_otp",
    })

    updated_transfer = _load_enriched_transfer(transfer_id, {
        **transfer,
        "buyerId": buyer_id,
        "sellerId": seller_id,
        "buyerOtpVerified": True,
        "sellerVerificationSid": seller_otp["sid"],
        "status": "pending_seller_otp",
    })

    _publish_seller_notification(transfer_id, seller_id)
    _broadcast_transfer_notification("buyer_verified", {
        "transferId": transfer_id,
        "buyerId": buyer_id,
        "sellerId": seller_id,
        "status": "pending_seller_otp",
    })

    return jsonify({"data": {
        **(updated_transfer or {}),
        "transferId": transfer_id,
        "status":     "pending_seller_otp",
        "message":    "Buyer verified. OTP sent to seller.",
    }}), 200


# ── POST /transfer/<id>/seller-accept ────────────────────────────────────────

@bp.post("/transfer/<transfer_id>/seller-accept")
@require_auth
def seller_accept(transfer_id):
    """
    Seller accepts the transfer request — OTP sent to seller
    ---
    tags:
      - Transfer
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: transfer_id
        required: true
        type: string
    responses:
      200:
        description: Accepted — status moves to pending_seller_otp
      400:
        description: Wrong transfer status
      401:
        description: Unauthorized
      403:
        description: You are not the seller
    """
    seller_id = request.user["userId"]

    transfer, err = call_service("GET", f"{TRANSFER_SERVICE}/transfers/{transfer_id}")
    if err:
        return _error("TRANSFER_NOT_FOUND", "Transfer not found.", 404)
    if transfer["sellerId"] != seller_id:
        return _error("AUTH_FORBIDDEN", "You are not the seller in this transfer.", 403)
    if transfer["status"] != "pending_seller_acceptance":
        return _error("VALIDATION_ERROR", "Transfer is not awaiting seller acceptance.", 400)

    seller, err = call_service("GET", f"{USER_SERVICE}/users/{transfer['sellerId']}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve seller details.", 503)

    otp_result, err = call_service("POST", f"{OTP_WRAPPER}/otp/send",
                                   json={"phoneNumber": seller["phoneNumber"]})
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not send OTP.", 503)

    call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={
        "sellerVerificationSid": otp_result["sid"],
        "status":                "pending_seller_otp",
    })
    updated_transfer = _load_enriched_transfer(transfer_id, {
        **transfer,
        "sellerVerificationSid": otp_result["sid"],
        "status": "pending_seller_otp",
    })
    
    # Broadcast seller acceptance
    _broadcast_transfer_notification("seller_accepted", {
        "transferId": transfer_id,
        "buyerId": transfer["buyerId"],
        "sellerId": seller_id,
        "status": "pending_seller_otp",
    })

    return jsonify({"data": {
        **(updated_transfer or {}),
        "transferId": transfer_id,
        "status":     "pending_seller_otp",
        "message":    "Request accepted. OTP sent to seller.",
    }}), 200


# ── POST /transfer/<id>/seller-reject ────────────────────────────────────────

@bp.post("/transfer/<transfer_id>/seller-reject")
@require_auth
def seller_reject(transfer_id):
    """
    Seller rejects the transfer request — listing and ticket reverted to active
    ---
    tags:
      - Transfer
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: transfer_id
        required: true
        type: string
        example: txr_001
    responses:
      200:
        description: Transfer rejected — listing back to active
        schema:
          type: object
          properties:
            data:
              type: object
              properties:
                transferId:
                  type: string
                  example: txr_001
                status:
                  type: string
                  example: cancelled
                message:
                  type: string
                  example: Transfer rejected.
      400:
        description: Transfer is not awaiting seller acceptance
      401:
        description: Unauthorized
      403:
        description: You are not the seller
      404:
        description: Transfer not found
    """
    seller_id = request.user["userId"]

    transfer, err = call_service("GET", f"{TRANSFER_SERVICE}/transfers/{transfer_id}")
    if err:
        return _error("TRANSFER_NOT_FOUND", "Transfer not found.", 404)
    if transfer["sellerId"] != seller_id:
        return _error("AUTH_FORBIDDEN", "You are not the seller in this transfer.", 403)
    if transfer["status"] != "pending_seller_acceptance":
        return _error("VALIDATION_ERROR", "Transfer is not awaiting seller acceptance.", 400)

    call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={"status": "cancelled"})
    listing, _ = call_service("GET", f"{MARKETPLACE_SERVICE}/listings/{transfer['listingId']}")
    if listing:
        call_service("PATCH", f"{MARKETPLACE_SERVICE}/listings/{transfer['listingId']}",
                     json={"status": "active"})
        call_service("PATCH", f"{TICKET_SERVICE}/tickets/{listing['ticketId']}",
                     json={"status": "listed"})
    
    # Broadcast seller rejection
    _broadcast_transfer_notification("seller_rejected", {
        "transferId": transfer_id,
        "buyerId": transfer["buyerId"],
        "sellerId": seller_id,
        "status": "cancelled",
    })

    return jsonify({"data": {"transferId": transfer_id, "status": "cancelled",
                             "message": "Transfer rejected."}}), 200


# ── POST /transfer/<id>/seller-verify ────────────────────────────────────────

@bp.post("/transfer/<transfer_id>/seller-verify")
@require_auth
def seller_verify(transfer_id):
    """
    Seller submits OTP — completes the transfer
    ---
    tags:
      - Transfer
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: transfer_id
        required: true
        type: string
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [otp]
          properties:
            otp:
              type: string
              example: "654321"
    responses:
      200:
        description: Transfer completed — ticket ownership transferred
      400:
        description: Invalid OTP or wrong transfer status
      401:
        description: Unauthorized
      402:
        description: Buyer no longer has sufficient credits
      500:
        description: Saga failed — no credits charged
    """
    seller_id = request.user["userId"]
    body      = request.get_json(silent=True) or {}

    if not body.get("otp"):
        return _error("VALIDATION_ERROR", "otp is required.", 400)

    transfer, err = call_service("GET", f"{TRANSFER_SERVICE}/transfers/{transfer_id}")
    if err:
        return _error("TRANSFER_NOT_FOUND", "Transfer not found.", 404)
    if transfer["sellerId"] != seller_id:
        return _error("AUTH_FORBIDDEN", "Access denied.", 403)
    if (
        transfer["status"] != "pending_seller_otp"
        or transfer.get("sellerOtpVerified")
        or not transfer.get("buyerOtpVerified")
        or not transfer.get("sellerVerificationSid")
    ):
        return _error("VALIDATION_ERROR", "Transfer is not awaiting seller OTP.", 400)

    seller, err = call_service("GET", f"{USER_SERVICE}/users/{transfer['sellerId']}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve seller details.", 503)

    verify, err = call_service("POST", f"{OTP_WRAPPER}/otp/verify", json={
        "sid": transfer["sellerVerificationSid"],
        "otp": body["otp"],
        "phoneNumber": seller["phoneNumber"],
    })
    if err or not verify.get("verified"):
        return _error("VALIDATION_ERROR", "OTP is incorrect or has expired.", 400)

    call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={
        "sellerOtpVerified": True,
    })

    buyer_id = transfer["buyerId"]
    credit_amount = transfer["creditAmount"]

    listing, _ = call_service("GET", f"{MARKETPLACE_SERVICE}/listings/{transfer['listingId']}")
    ticket_id = listing["ticketId"] if listing else None

    buyer_credit, err = call_credit_service("GET", f"/credits/{buyer_id}")
    if err:
        call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={"status": "failed"})
        return _error("SERVICE_UNAVAILABLE", "Could not verify buyer balance.", 503)

    buyer_balance = _get_credit_balance(buyer_credit)
    if buyer_balance < credit_amount:
        call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={"status": "failed"})
        return _error("INSUFFICIENT_CREDITS", "Buyer no longer has sufficient credits.", 402)

    seller_credit, seller_err = call_credit_service("GET", f"/credits/{seller_id}")
    if seller_err:
        return _error("SERVICE_UNAVAILABLE", "Could not verify seller balance.", 503)
    seller_balance = _get_credit_balance(seller_credit)

    try:
        _execute_saga(
            transfer_id=transfer_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            credit_amount=credit_amount,
            ticket_id=ticket_id,
            listing_id=transfer["listingId"],
            buyer_balance=buyer_balance,
            seller_balance=seller_balance,
        )

        completed_transfer = {
            "transferId": transfer_id,
            "listingId": transfer["listingId"],
            "buyerId": buyer_id,
            "sellerId": seller_id,
            "ticketId": ticket_id,
            "status": "completed",
        }

        transfer_payload = _build_transfer_notification_payload("transfer_completed", completed_transfer)
        _broadcast_notification("transfer_update", transfer_payload)

        ticket_payload = {
            "eventType": "ticket_transferred",
            "ticketId": ticket_id,
            "ownerId": buyer_id,
            "previousOwnerId": seller_id,
            "transferId": transfer_id,
            "event": transfer_payload.get("event"),
            "eventName": transfer_payload.get("eventName"),
        }
        _broadcast_notification(
            "ticket_update",
            {key: value for key, value in ticket_payload.items() if value is not None},
        )
    except Exception:
        return _error("INTERNAL_ERROR", "Transfer failed — no credits were charged.", 500)

    completed_at = datetime.now(timezone.utc).isoformat()
    updated_transfer = _load_enriched_transfer(transfer_id, {
        **transfer,
        "buyerId": buyer_id,
        "sellerId": seller_id,
        "ticketId": ticket_id,
        "buyerOtpVerified": True,
        "sellerOtpVerified": True,
        "status": "completed",
        "completedAt": completed_at,
    })

    return jsonify({"data": {
        **(updated_transfer or {}),
        "transferId":  transfer_id,
        "status":      "completed",
        "completedAt": (updated_transfer or {}).get("completedAt", completed_at),
        "ticket": {"ticketId": ticket_id, "newOwnerId": buyer_id, "status": "active"},
    }}), 200


# ── Helper: Enrich Transfer ──────────────────────────────────────────────────

def _enrich_transfer(transfer):
    """
    Enrich a transfer record with seller name, ticket, event, and seat details.
    Tolerates partial downstream failures without collapsing the full response.
    """
    enriched = transfer.copy()

    context = _build_transfer_context(transfer)
    buyer = context["buyer"] or {}
    seller = context["seller"] or {}
    event_payload = _build_event_payload(context)
    seat_payload = _build_seat_payload(context)
    venue = context["venue"]

    enriched["buyerName"] = _first_present(
        buyer.get("name"),
        buyer.get("fullName"),
        buyer.get("email"),
        "Buyer",
    )
    enriched["sellerName"] = _first_present(
        seller.get("name"),
        seller.get("fullName"),
        seller.get("email"),
        "Seller",
    )
    enriched["ticketId"] = context["ticketId"]
    if context["listing"]:
        enriched["listing"] = context["listing"]
    if context["ticket"]:
        enriched["ticket"] = context["ticket"]
    if venue:
        enriched["venue"] = venue
        enriched["venueName"] = venue.get("name")
    if event_payload:
        enriched["event"] = event_payload
        enriched["eventName"] = event_payload.get("name")
        enriched["eventDate"] = event_payload.get("date")
        enriched["eventImage"] = event_payload.get("image")
    if seat_payload:
        enriched["seat"] = seat_payload
        enriched["seatSection"] = seat_payload.get("section")
        enriched["seatRow"] = seat_payload.get("row")
        enriched["seatNumber"] = seat_payload.get("seat")
        enriched["seatGate"] = seat_payload.get("gate")

    return enriched


# ── GET /transfer/pending ─────────────────────────────────────────────────────

@bp.get("/transfer/pending")
@require_auth
def get_pending_transfers():
    """
    Get all pending transfers awaiting the authenticated seller's action
    ---
    tags:
      - Transfer
    security:
      - BearerAuth: []
    responses:
      200:
        description: List of enriched transfers with status pending_seller_acceptance
        schema:
          type: object
          properties:
            data:
              type: object
              properties:
                transfers:
                  type: array
                  items:
                    type: object
                    properties:
                      transferId:
                        type: string
                        example: txr_001
                      buyerId:
                        type: string
                        example: usr_001
                      sellerId:
                        type: string
                        example: usr_002
                      sellerName:
                        type: string
                        example: John Doe
                      creditAmount:
                        type: number
                        example: 80.0
                      status:
                        type: string
                        example: pending_seller_acceptance
                      event:
                        type: object
                      seat:
                        type: object
      401:
        description: Unauthorized
      503:
        description: Transfer service unavailable
    """
    seller_id = request.user["userId"]
    pending_statuses = ["pending_seller_otp", "pending_seller_acceptance"]
    transfers = []
    for pending_status in pending_statuses:
        result, err = call_service("GET", f"{TRANSFER_SERVICE}/transfers",
                                   params={"sellerId": seller_id, "status": pending_status})
        if err:
            return _error("SERVICE_UNAVAILABLE", "Could not retrieve transfers.", 503)
        transfers.extend(result.get("transfers", []))

    unique_transfers = {transfer["transferId"]: transfer for transfer in transfers}
    enriched_transfers = [_enrich_transfer(t) for t in unique_transfers.values()]
    
    return jsonify({"data": {"transfers": enriched_transfers}}), 200


# ── GET /transfer/my-pending ──────────────────────────────────────────────────

@bp.get("/transfer/my-pending")
@require_auth
def get_my_pending_transfers():
    """
    Get all transfers where the authenticated buyer has a pending OTP to enter
    ---
    tags:
      - Transfer
    security:
      - BearerAuth: []
    responses:
      200:
        description: List of enriched transfers with status pending_buyer_otp
        schema:
          type: object
          properties:
            data:
              type: object
              properties:
                transfers:
                  type: array
                  items:
                    type: object
                    properties:
                      transferId:
                        type: string
                        example: txr_001
                      buyerId:
                        type: string
                        example: usr_001
                      sellerId:
                        type: string
                        example: usr_002
                      sellerName:
                        type: string
                        example: John Doe
                      creditAmount:
                        type: number
                        example: 80.0
                      status:
                        type: string
                        example: pending_buyer_otp
                      event:
                        type: object
                      seat:
                        type: object
      401:
        description: Unauthorized
      503:
        description: Transfer service unavailable
    """
    buyer_id = request.user["userId"]
    result, err = call_service("GET", f"{TRANSFER_SERVICE}/transfers",
                               params={"buyerId": buyer_id, "status": "pending_buyer_otp"})
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve transfers.", 503)
    
    # Enrich each transfer
    transfers = result.get("transfers", [])
    enriched_transfers = [_enrich_transfer(t) for t in transfers]
    
    return jsonify({"data": {"transfers": enriched_transfers}}), 200


# ── GET /transfer/history ─────────────────────────────────────────────────────

@bp.get("/transfer/history")
@require_auth
def get_transfer_history():
    """
    Get completed transfers initiated by the authenticated seller
    ---
    tags:
      - Transfer
    security:
      - BearerAuth: []
    responses:
      200:
        description: List of enriched completed transfers for seller archive/history views
      401:
        description: Unauthorized
      503:
        description: Transfer service unavailable
    """
    seller_id = request.user["userId"]
    result, err = call_service(
        "GET",
        f"{TRANSFER_SERVICE}/transfers",
        params={"sellerId": seller_id, "status": "completed"},
    )
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve transfer history.", 503)

    transfers = result.get("transfers", [])
    enriched_transfers = [_enrich_transfer(t) for t in transfers]

    return jsonify({"data": {"transfers": enriched_transfers}}), 200


# ── GET /transfer/<id> ────────────────────────────────────────────────────────

@bp.get("/transfer/<transfer_id>")
@require_auth
def get_transfer(transfer_id):
    """
    Get transfer status — accessible by buyer and seller only
    ---
    tags:
      - Transfer
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: transfer_id
        required: true
        type: string
    responses:
      200:
        description: Transfer record enriched with ticket and event details
      401:
        description: Unauthorized
      403:
        description: Access denied — not buyer or seller
      404:
        description: Transfer not found
    """
    user_id  = request.user["userId"]
    transfer, err = call_service("GET", f"{TRANSFER_SERVICE}/transfers/{transfer_id}")
    if err:
        return _error("TRANSFER_NOT_FOUND", "Transfer not found.", 404)
    if user_id not in (transfer["buyerId"], transfer["sellerId"]):
        return _error("AUTH_FORBIDDEN", "Access denied.", 403)
    
    # Enrich transfer using shared enrichment adapter
    enriched_transfer = _enrich_transfer(transfer)
    
    return jsonify({"data": enriched_transfer}), 200


# ── POST /transfer/<id>/resend-otp ───────────────────────────────────────────

@bp.post("/transfer/<transfer_id>/resend-otp")
@require_auth
def resend_otp(transfer_id):
    """
    Resend OTP to the buyer or seller depending on current transfer status
    ---
    tags:
      - Transfer
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: transfer_id
        required: true
        type: string
        example: txr_001
    responses:
      200:
        description: OTP resent successfully
        schema:
          type: object
          properties:
            data:
              type: object
              properties:
                message:
                  type: string
                  example: OTP resent to your phone.
      400:
        description: OTP resend not available for current transfer status
      401:
        description: Unauthorized
      403:
        description: Access denied — not buyer or seller
      404:
        description: Transfer not found
      503:
        description: OTP service unavailable
    """
    user_id = request.user["userId"]

    transfer, err = call_service("GET", f"{TRANSFER_SERVICE}/transfers/{transfer_id}")
    if err:
        return _error("TRANSFER_NOT_FOUND", "Transfer not found.", 404)
    if user_id not in (transfer["buyerId"], transfer["sellerId"]):
        return _error("AUTH_FORBIDDEN", "Access denied.", 403)

    status = transfer.get("status")

    if status == "pending_buyer_otp" and transfer["buyerId"] == user_id:
        buyer, err = call_service("GET", f"{USER_SERVICE}/users/{transfer['buyerId']}")
        if err:
            return _error("SERVICE_UNAVAILABLE", "Could not retrieve user details.", 503)
        otp_result, err = call_service("POST", f"{OTP_WRAPPER}/otp/send",
                                       json={"phoneNumber": buyer["phoneNumber"]})
        if err:
            return _error("SERVICE_UNAVAILABLE", "Could not send OTP.", 503)
        call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}",
                     json={"buyerVerificationSid": otp_result["sid"]})
        return jsonify({"data": {"message": "OTP resent to your phone."}}), 200

    elif status == "pending_seller_otp" and transfer["sellerId"] == user_id:
        seller, err = call_service("GET", f"{USER_SERVICE}/users/{transfer['sellerId']}")
        if err:
            return _error("SERVICE_UNAVAILABLE", "Could not retrieve user details.", 503)
        otp_result, err = call_service("POST", f"{OTP_WRAPPER}/otp/send",
                                       json={"phoneNumber": seller["phoneNumber"]})
        if err:
            return _error("SERVICE_UNAVAILABLE", "Could not send OTP.", 503)
        call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}",
                     json={"sellerVerificationSid": otp_result["sid"]})
        return jsonify({"data": {"message": "OTP resent to your phone."}}), 200

    return _error("VALIDATION_ERROR", "OTP resend is not available for the current transfer state.", 400)


# ── POST /transfer/<id>/cancel ────────────────────────────────────────────────

@bp.post("/transfer/<transfer_id>/cancel")
@require_auth
def cancel_transfer(transfer_id):
    """
    Cancel an in-progress transfer — reverts listing and ticket to active
    ---
    tags:
      - Transfer
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: transfer_id
        required: true
        type: string
    responses:
      200:
        description: Transfer cancelled
      400:
        description: Transfer already completed or ended
      401:
        description: Unauthorized
      403:
        description: Access denied
    """
    user_id  = request.user["userId"]
    transfer, err = call_service("GET", f"{TRANSFER_SERVICE}/transfers/{transfer_id}")
    if err:
        return _error("TRANSFER_NOT_FOUND", "Transfer not found.", 404)
    if user_id not in (transfer["buyerId"], transfer["sellerId"]):
        return _error("AUTH_FORBIDDEN", "Access denied.", 403)
    if transfer["status"] == "completed":
        return _error("VALIDATION_ERROR", "Completed transfers cannot be cancelled.", 400)
    if transfer["status"] in ("cancelled", "failed"):
        return _error("VALIDATION_ERROR", "Transfer has already ended.", 400)

    call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={"status": "cancelled"})

    listing, _ = call_service("GET", f"{MARKETPLACE_SERVICE}/listings/{transfer['listingId']}")
    if listing:
        call_service("PATCH", f"{MARKETPLACE_SERVICE}/listings/{transfer['listingId']}",
                     json={"status": "active"})
        call_service("PATCH", f"{TICKET_SERVICE}/tickets/{listing['ticketId']}",
                     json={"status": "listed"})
    
    # Broadcast transfer cancellation
    _broadcast_transfer_notification("transfer_cancelled", {
        "transferId": transfer_id,
        "buyerId": transfer["buyerId"],
        "sellerId": transfer["sellerId"],
        "status": "cancelled",
    })

    return jsonify({"data": {"transferId": transfer_id, "status": "cancelled"}}), 200
