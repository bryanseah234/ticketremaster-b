"""
Inventory Service — Main entry point
Starts gRPC server + RabbitMQ consumer in a separate daemon thread.
Phase 6: Implement full startup pattern.
See INSTRUCTIONS.md Section 8 for the startup pattern.
"""

import threading
from flask import Flask, jsonify
from datetime import datetime, timezone


def create_health_app():
    """Minimal Flask app for Docker health checks on port 8080."""
    app = Flask(__name__)

    @app.route("/health")
    def health():
        return jsonify({
            "status": "healthy",
            "service": "inventory-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "database": "not_configured",
                "rabbitmq": "not_configured",
            },
        })

    return app


def main():
    # Phase 6: Start gRPC server
    # grpc_server = create_grpc_server()
    # grpc_server.start()

    # Phase 6: Start RabbitMQ consumer in a separate thread
    # consumer_thread = threading.Thread(
    #     target=start_consumer,
    #     args=(db_session_factory,),
    #     daemon=True
    # )
    # consumer_thread.start()

    # Start HTTP health endpoint on port 8080
    health_app = create_health_app()
    health_app.run(host="0.0.0.0", port=8080, debug=False)


if __name__ == "__main__":
    main()
