"""
Transfer Timeout Consumer.

Consumes transfer_timeout_queue messages to auto-cancel stuck transfers.
Transfers that are not completed within 24 hours are automatically cancelled.
"""
import json
import logging
import os
import time
from datetime import datetime, timezone

import pika

from service_client import call_service

logger = logging.getLogger(__name__)

TRANSFER_TIMEOUT_HOURS = int(os.environ.get("TRANSFER_TIMEOUT_HOURS", "24"))
TRANSFER_SERVICE = os.environ.get("TRANSFER_SERVICE_URL", "http://transfer-service:5000")
MARKETPLACE_SERVICE = os.environ.get("MARKETPLACE_SERVICE_URL", "http://marketplace-service:5000")


def _get_connection():
    return pika.BlockingConnection(pika.ConnectionParameters(
        host=os.environ.get("RABBITMQ_HOST", "rabbitmq"),
        port=int(os.environ.get("RABBITMQ_PORT", "5672")),
        credentials=pika.PlainCredentials(
            os.environ.get("RABBITMQ_USER", "guest"),
            os.environ.get("RABBITMQ_PASS", "guest"),
        ),
        connection_attempts=5,
        retry_delay=3,
    ))


def _cancel_transfer(transfer_id, listing_id):
    """
    Cancel a stuck transfer and return listing to active status.
    """
    try:
        # Update transfer status to cancelled
        call_service("PATCH", f"{TRANSFER_SERVICE}/transfers/{transfer_id}", json={
            "status": "cancelled",
            "cancelledAt": datetime.now(timezone.utc).isoformat(),
            "cancelReason": "timeout",
        })

        # Return listing to active status
        call_service("PATCH", f"{MARKETPLACE_SERVICE}/listings/{listing_id}", json={
            "status": "active",
        })
        
        logger.info("Auto-cancelled transfer %s and reactivated listing %s", transfer_id, listing_id)
        return True
    except Exception as exc:
        logger.error("Failed to cancel transfer %s: %s", transfer_id, exc)
        return False


def start_transfer_timeout_consumer():
    """Blocking consumer — run in a daemon thread."""
    while True:
        try:
            connection = _get_connection()
            channel    = connection.channel()

            def on_timeout_message(ch, method, _properties, body):
                try:
                    data = json.loads(body)
                    transfer_id = data.get("transferId", "")
                    listing_id = data.get("listingId", "")
                    buyer_id = data.get("buyerId", "")
                    seller_id = data.get("sellerId", "")
                    
                    logger.info("Processing transfer timeout: transfer=%s", transfer_id)
                    
                    # Check if transfer is still in pending state
                    transfer, err = call_service("GET", f"{TRANSFER_SERVICE}/transfers/{transfer_id}")
                    if err:
                        logger.warning("Transfer %s not found, skipping cancellation", transfer_id)
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        return

                    # Only cancel if still pending (not completed or already cancelled)
                    if transfer.get("status") not in ["pending_seller_acceptance", "pending_buyer_otp", "pending_seller_otp"]:
                        logger.info("Transfer %s already in status %s, skipping cancellation", transfer_id, transfer.get("status"))
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        return
                    
                    # Cancel the transfer
                    _cancel_transfer(transfer_id, listing_id)
                    
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:
                    logger.error("Transfer timeout consumer handler error: %s", exc)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="transfer_timeout_queue", on_message_callback=on_timeout_message)
            logger.info("Transfer timeout consumer started")
            channel.start_consuming()
        except Exception as exc:
            logger.warning("Transfer timeout consumer disconnected: %s — retrying in 5s", exc)
            time.sleep(5)
