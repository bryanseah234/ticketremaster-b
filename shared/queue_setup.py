"""
RabbitMQ queue topology setup for TicketRemaster.

Declares:
  - seat_hold_ttl_queue: Messages expire after SEAT_HOLD_DURATION_SECONDS (default 600s).
    On expiry, messages are routed to the dead letter exchange.
  - seat_hold_dlx (exchange): Dead letter exchange that receives expired hold messages.
  - seat_hold_expired_queue: Bound to the DLX. Consumer releases the seat via gRPC.
  - seller_notification_queue: Notifies seller when a buyer verifies OTP during P2P transfer.

Call this module on startup of Ticket Purchase Orchestrator and Transfer Orchestrator:
    python -m shared.queue_setup
    OR
    from shared.queue_setup import declare_queues; declare_queues()
"""

import os

import pika


def get_connection_params():
    return pika.ConnectionParameters(
        host=os.getenv('RABBITMQ_HOST', 'rabbitmq'),
        port=int(os.getenv('RABBITMQ_PORT', '5672')),
        credentials=pika.PlainCredentials(
            username=os.getenv('RABBITMQ_USER', 'guest'),
            password=os.getenv('RABBITMQ_PASS', 'guest'),
        ),
        connection_attempts=5,
        retry_delay=3,
    )


def declare_queues(channel=None):
    close_after = False
    if channel is None:
        connection = pika.BlockingConnection(get_connection_params())
        channel = connection.channel()
        close_after = True

    hold_ttl_ms = int(os.getenv('SEAT_HOLD_DURATION_SECONDS', '600')) * 1000

    # Dead letter exchange for expired seat holds
    channel.exchange_declare(
        exchange='seat_hold_dlx',
        exchange_type='fanout',
        durable=True,
    )

    # Queue that receives expired hold messages
    channel.queue_declare(
        queue='seat_hold_expired_queue',
        durable=True,
    )
    channel.queue_bind(
        queue='seat_hold_expired_queue',
        exchange='seat_hold_dlx',
    )

    # TTL queue for seat holds — messages expire and route to DLX
    channel.queue_declare(
        queue='seat_hold_ttl_queue',
        durable=True,
        arguments={
            'x-message-ttl': hold_ttl_ms,
            'x-dead-letter-exchange': 'seat_hold_dlx',
        },
    )

    # Seller notification queue for P2P transfer flow
    channel.queue_declare(
        queue='seller_notification_queue',
        durable=True,
    )

    print(
        f'Queue setup complete. '
        f'TTL={hold_ttl_ms}ms, '
        f'DLX=seat_hold_dlx, '
        f'Queues: seat_hold_ttl_queue, seat_hold_expired_queue, seller_notification_queue'
    )

    if close_after:
        connection.close()


if __name__ == '__main__':
    declare_queues()
