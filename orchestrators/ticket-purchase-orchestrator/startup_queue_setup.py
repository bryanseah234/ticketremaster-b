"""Queue bootstrap for ticket-purchase-orchestrator.

Run this during orchestrator startup to ensure RabbitMQ topology exists.
"""

from shared.queue_setup import declare_queues


def bootstrap():
    declare_queues()


if __name__ == '__main__':
    bootstrap()
