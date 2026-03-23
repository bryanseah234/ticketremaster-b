"""
Seller Notification Consumer.

Consumes seller_notification_queue messages published after buyer OTP verification.
Since seller notification is implemented via frontend polling (GET /transfer/<id>),
the status was already set to pending_seller_acceptance in buyer-verify.
This consumer acks the message — the status change is the notification mechanism.
"""
import json
import logging
import os
import time

import pika

logger = logging.getLogger(__name__)


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


def start_seller_consumer():
    """Blocking consumer — run in a daemon thread."""
    while True:
        try:
            connection = _get_connection()
            channel    = connection.channel()

            def on_notification(ch, method, _properties, body):
                try:
                    data = json.loads(body)
                    logger.info(
                        "Seller notified: transfer=%s seller=%s",
                        data.get("transferId"), data.get("sellerId"),
                    )
                    # Transfer status is already pending_seller_acceptance —
                    # frontend polls GET /transfer/<id> to see the status change.
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:
                    logger.error("Seller consumer handler error: %s", exc)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="seller_notification_queue", on_message_callback=on_notification)
            logger.info("Seller notification consumer started")
            channel.start_consuming()
        except Exception as exc:
            logger.warning("Seller consumer disconnected: %s — retrying in 5s", exc)
            time.sleep(5)
