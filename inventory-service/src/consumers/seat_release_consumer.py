"""
Seat Release Consumer — RabbitMQ DLX consumer
Listens to seat.release.queue for expired hold messages.
On message: releases the seat and marks the order as FAILED.
"""

import json
import os
import time
import logging
import requests
import pika

from src.db import get_session
from src.services.lock_service import release_seat

logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "guest")
ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://order-service:5001")

QUEUE_NAME = "seat.release.queue"
RECONNECT_DELAY = 5  # seconds


def _on_message(channel, method, properties, body):
    """Callback for each message from the seat.release.queue."""
    try:
        message = json.loads(body)
        seat_id = message.get("seat_id")
        order_id = message.get("order_id")

        logger.info(f"Received seat release message: seat_id={seat_id}, order_id={order_id}")

        if not seat_id:
            logger.error("Missing seat_id in release message, acking to discard")
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Step 1: Release the seat back to AVAILABLE
        with get_session() as session:
            success, error = release_seat(session, seat_id)

        if success:
            logger.info(f"Seat {seat_id} released successfully")
        else:
            logger.warning(f"Seat {seat_id} release returned: {error} (may already be released)")

        # Step 2: Mark the order as FAILED via HTTP call to Order Service
        if order_id:
            try:
                resp = requests.patch(
                    f"{ORDER_SERVICE_URL}/orders/{order_id}/status",
                    json={"status": "FAILED"},
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    logger.info(f"Order {order_id} marked as FAILED")
                else:
                    logger.warning(f"Order Service returned {resp.status_code}: {resp.text}")
            except requests.RequestException as e:
                logger.error(f"Failed to update order {order_id}: {e}")
                # Nack and requeue so we can retry
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return

        # Success — acknowledge the message
        channel.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in release message: {e}")
        # Bad message — ack to discard (won't get better on retry)
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing release message: {e}", exc_info=True)
        # Nack and requeue for retry
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consumer():
    """
    Start the RabbitMQ consumer with auto-reconnect loop.
    This function blocks — run it in a daemon thread.
    """
    while True:
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            params = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            # Ensure queue exists (should already be declared via definitions.json)
            channel.queue_declare(queue=QUEUE_NAME, durable=True, passive=True)

            # Prefetch 1 message at a time for fair dispatch
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_message)

            logger.info(f"Seat release consumer started, listening on {QUEUE_NAME}")
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"RabbitMQ connection error: {e}, reconnecting in {RECONNECT_DELAY}s...")
            time.sleep(RECONNECT_DELAY)
        except Exception as e:
            logger.error(f"Consumer error: {e}, reconnecting in {RECONNECT_DELAY}s...", exc_info=True)
            time.sleep(RECONNECT_DELAY)
