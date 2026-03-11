import pika
import json
import logging
import os

logger = logging.getLogger("orchestrator")
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", 5672))

def publish_seat_hold_ttl(seat_id, user_id, order_id, reserved_at):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
        )
        channel = connection.channel()
        message = {
            "seat_id": seat_id,
            "user_id": user_id,
            "order_id": order_id,
            "reserved_at": reserved_at
        }
        channel.basic_publish(
            exchange='seat.hold.exchange',
            routing_key='seat.hold',
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2, # make message persistent
            )
        )
        connection.close()
        logger.info(f"Published TTL message to RabbitMQ for seat {seat_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish TTL to RabbitMQ: {str(e)}")
        return False
