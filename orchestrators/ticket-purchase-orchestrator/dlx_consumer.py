"""
DLX Consumer for ticket-purchase-orchestrator.

Listens on seat_hold_expired_queue and releases the held seat via gRPC
when the per-message TTL lapses in seat_hold_ttl_queue.
"""
import json
import logging
import os
import time

import grpc
import pika

import seat_inventory_pb2
import seat_inventory_pb2_grpc

logger = logging.getLogger(__name__)


def _grpc_stub():
    host = os.environ.get("SEAT_INVENTORY_GRPC_HOST", "seat-inventory-service")
    port = os.environ.get("SEAT_INVENTORY_GRPC_PORT", "50051")
    channel = grpc.insecure_channel(f"{host}:{port}")
    return seat_inventory_pb2_grpc.SeatInventoryServiceStub(channel)


def _get_connection():
    params = pika.ConnectionParameters(
        host=os.environ.get("RABBITMQ_HOST", "rabbitmq"),
        port=int(os.environ.get("RABBITMQ_PORT", "5672")),
        credentials=pika.PlainCredentials(
            username=os.environ.get("RABBITMQ_USER", "guest"),
            password=os.environ.get("RABBITMQ_PASS", "guest"),
        ),
        connection_attempts=5,
        retry_delay=3,
    )
    return pika.BlockingConnection(params)


def start_dlx_consumer():
    """Blocking consumer — run in a daemon thread."""
    while True:
        try:
            connection = _get_connection()
            channel    = connection.channel()
            stub       = _grpc_stub()

            def on_expired(ch, method, _properties, body):
                try:
                    data         = json.loads(body)
                    inventory_id = data.get("inventoryId", "")
                    user_id      = data.get("userId", "")
                    hold_token   = data.get("holdToken", "")
                    logger.info("DLX: releasing hold on %s", inventory_id)
                    stub.ReleaseSeat(seat_inventory_pb2.ReleaseSeatRequest(
                        inventory_id=inventory_id,
                        user_id=user_id,
                        hold_token=hold_token,
                    ))
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:
                    logger.error("DLX handler error: %s", exc)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="seat_hold_expired_queue", on_message_callback=on_expired)
            logger.info("DLX consumer started on seat_hold_expired_queue")
            channel.start_consuming()
        except Exception as exc:
            logger.warning("DLX consumer disconnected: %s — retrying in 5s", exc)
            time.sleep(5)
