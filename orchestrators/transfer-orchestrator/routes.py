"""
Transfer Orchestrator routes.

P2P transfer flow:
  POST /transfer/initiate            buyer initiates
  POST /transfer/<id>/seller-accept  seller accepts → buyer OTP sent
  POST /transfer/<id>/buyer-verify   buyer submits OTP → seller notified via queue
  POST /transfer/<id>/seller-verify  seller submits OTP → saga executes
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
        call_service("PATCH", f"{MARKETPLACE_SERVICE}/listings/{listing_id}", json={"status": "completed"})
        completed.append("listing_completed")

        # 7. Complete transfer
        call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={
            "status": "completed",
            "completedAt": datetime.now(timezone.utc).isoformat(),
        })
        completed.append("transfer_completed")

    except Exception as exc:
        logger.error("Saga failed at step %d (%s completed): %s", len(completed), ", ".join(completed), exc)
        
        # Reverse compensation in reverse order
        try:
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
        description: Transfer created — status pending_seller_acceptance
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

    _publish_seller_notification(transfer["transferId"], seller_id)
    
    # Schedule timeout for auto-cancellation
    _publish_transfer_timeout(
        transfer["transferId"],
        body["listingId"],
        buyer_id,
        seller_id,
    )

    return jsonify({"data": {
        "transferId": transfer["transferId"],
        "status":     "pending_seller_acceptance",
        "message":    "Request sent to seller. Pending acceptance.",
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
        description: OTP verified — status moves to pending_seller_otp
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
    if transfer["status"] != "pending_buyer_otp":
        return _error("VALIDATION_ERROR", "Transfer is not awaiting buyer OTP.", 400)

    verify, err = call_service("POST", f"{OTP_WRAPPER}/otp/verify", json={
        "sid": transfer["buyerVerificationSid"],
        "otp": body["otp"],
    })
    if err or not verify.get("verified"):
        return _error("VALIDATION_ERROR", "OTP is incorrect or has expired.", 400)

    # Send OTP to seller now
    seller, err = call_service("GET", f"{USER_SERVICE}/users/{transfer['sellerId']}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve seller details.", 503)

    seller_otp, err = call_service("POST", f"{OTP_WRAPPER}/otp/send",
                                   json={"phoneNumber": seller["phoneNumber"]})
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not send OTP to seller.", 503)

    call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={
        "buyerOtpVerified":      True,
        "sellerVerificationSid": seller_otp["sid"],
        "status":                "pending_seller_otp",
    })

    return jsonify({"data": {
        "transferId": transfer_id,
        "status":     "pending_seller_otp",
        "message":    "Your OTP verified. OTP sent to seller.",
    }}), 200


# ── POST /transfer/<id>/seller-accept ────────────────────────────────────────

@bp.post("/transfer/<transfer_id>/seller-accept")
@require_auth
def seller_accept(transfer_id):
    """
    Seller accepts the transfer request — OTP sent to buyer
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
        description: Accepted — status moves to pending_buyer_otp
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

    # Send OTP to buyer first
    buyer, err = call_service("GET", f"{USER_SERVICE}/users/{transfer['buyerId']}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve buyer details.", 503)

    otp_result, err = call_service("POST", f"{OTP_WRAPPER}/otp/send",
                                   json={"phoneNumber": buyer["phoneNumber"]})
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not send OTP.", 503)

    call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={
        "buyerVerificationSid": otp_result["sid"],
        "status":               "pending_buyer_otp",
    })

    return jsonify({"data": {
        "transferId": transfer_id,
        "status":     "pending_buyer_otp",
        "message":    "Request accepted. OTP sent to buyer.",
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

    return jsonify({"data": {"transferId": transfer_id, "status": "cancelled",
                             "message": "Transfer rejected."}}), 200


# ── POST /transfer/<id>/seller-verify ────────────────────────────────────────

@bp.post("/transfer/<transfer_id>/seller-verify")
@require_auth
def seller_verify(transfer_id):
    """
    Seller submits OTP — executes the full transfer saga
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
    if transfer["status"] != "pending_seller_otp" or transfer.get("sellerOtpVerified"):
        return _error("VALIDATION_ERROR", "Transfer is not awaiting seller OTP.", 400)

    verify, err = call_service("POST", f"{OTP_WRAPPER}/otp/verify", json={
        "sid": transfer["sellerVerificationSid"],
        "otp": body["otp"],
    })
    if err or not verify.get("verified"):
        return _error("VALIDATION_ERROR", "OTP is incorrect or has expired.", 400)

    call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}",
                 json={"sellerOtpVerified": True})

    buyer_id      = transfer["buyerId"]
    credit_amount = transfer["creditAmount"]

    # Fetch listing to get ticket_id
    listing, _ = call_service("GET", f"{MARKETPLACE_SERVICE}/listings/{transfer['listingId']}")
    ticket_id  = listing["ticketId"] if listing else None

    # Re-check buyer balance immediately before executing
    buyer_credit, err = call_credit_service("GET", f"/credits/{buyer_id}")
    if err:
        call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={"status": "failed"})
        return _error("SERVICE_UNAVAILABLE", "Could not verify buyer balance.", 503)

    buyer_balance = _get_credit_balance(buyer_credit)
    if buyer_balance < credit_amount:
        call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={"status": "failed"})
        return _error("INSUFFICIENT_CREDITS", "Buyer no longer has sufficient credits.", 402)

    seller_credit, seller_err = call_credit_service("GET", f"/credits/{seller_id}")
    seller_balance = _get_credit_balance(seller_credit) if not seller_err and seller_credit else 0.0

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
    except Exception:
        return _error("INTERNAL_ERROR", "Transfer failed — no credits were charged.", 500)

    return jsonify({"data": {
        "transferId":  transfer_id,
        "status":      "completed",
        "completedAt": datetime.now(timezone.utc).isoformat(),
        "ticket": {"ticketId": ticket_id, "newOwnerId": buyer_id, "status": "active"},
    }}), 200


# ── GET /transfer/pending ─────────────────────────────────────────────────────

@bp.get("/transfer/pending")
@require_auth
def get_pending_transfers():
    """
    Get all pending transfers awaiting the authenticated seller's acceptance
    ---
    tags:
      - Transfer
    security:
      - BearerAuth: []
    responses:
      200:
        description: List of transfers with status pending_seller_acceptance
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
                      creditAmount:
                        type: number
                        example: 80.0
                      status:
                        type: string
                        example: pending_seller_acceptance
      401:
        description: Unauthorized
      503:
        description: Transfer service unavailable
    """
    seller_id = request.user["userId"]
    result, err = call_service("GET", f"{TRANSFER_SERVICE}/transfers",
                               params={"sellerId": seller_id, "status": "pending_seller_acceptance"})
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve transfers.", 503)
    return jsonify({"data": {"transfers": result.get("transfers", [])}}), 200


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
        description: Transfer record
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
    return jsonify({"data": transfer}), 200


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

    return jsonify({"data": {"transferId": transfer_id, "status": "cancelled"}}), 200