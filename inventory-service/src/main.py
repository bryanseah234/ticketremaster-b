"""
Inventory Service — Main entry point
Starts gRPC server + RabbitMQ consumer in a separate daemon thread + Flask health app.
"""

import os
import threading
import logging
from flask import Flask, jsonify, request as flask_request
from datetime import datetime, timezone

import pika

from src.db import get_session, engine
from src.models.seat import Seat
from src.grpc_server import create_grpc_server
from src.consumers.seat_release_consumer import start_consumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("inventory-service")

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "guest")


def check_db_health():
    """Check database connectivity."""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def check_rabbitmq():
    """Check RabbitMQ connectivity."""
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        params = pika.ConnectionParameters(
            host=RABBITMQ_HOST, credentials=credentials, connection_attempts=1, retry_delay=0,
            socket_timeout=2,
        )
        connection = pika.BlockingConnection(params)
        connection.close()
        return True
    except Exception:
        return False


def create_health_app():
    """Flask app for Docker health checks on port 8080 + internal HTTP sidecar."""
    app = Flask(__name__)

    @app.route("/health")
    def health():
        db_ok = check_db_health()
        rmq_ok = check_rabbitmq()

        # DB is the primary health indicator for Docker health checks.
        # RabbitMQ is informational — the consumer thread handles reconnects.
        return jsonify({
            "status": "healthy" if db_ok else "unhealthy",
            "service": "inventory-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "database": "connected" if db_ok else "disconnected",
                "rabbitmq": "connected" if rmq_ok else "disconnected",
            },
        }), 200 if db_ok else 503

    @app.route("/internal/seats")
    def get_seats():
        """HTTP sidecar endpoint — returns seats for an event. Used by Event Service."""
        event_id = flask_request.args.get("event_id")
        if not event_id:
            return jsonify({"error": "event_id is required"}), 400

        with get_session() as session:
            seats = session.query(Seat).filter(Seat.event_id == event_id).all()
            data = [seat.to_dict() for seat in seats]

        return jsonify({"data": data})

    return app


def main():
    logger.info("Starting Inventory Service...")

    # 1. Start gRPC server
    grpc_server = create_grpc_server()
    grpc_server.start()
    logger.info("gRPC server started on port 50051")

    # 2. Start RabbitMQ consumer in a separate daemon thread
    consumer_thread = threading.Thread(
        target=start_consumer,
        daemon=True,
        name="seat-release-consumer",
    )
    consumer_thread.start()
    logger.info("Seat release consumer thread started")

    # 3. Start HTTP health/sidecar endpoint on port 8080 (blocks)
    health_app = create_health_app()
    logger.info("Starting health/sidecar HTTP server on port 8080")
    health_app.run(host="0.0.0.0", port=8080, debug=False)


if __name__ == "__main__":
    main()
