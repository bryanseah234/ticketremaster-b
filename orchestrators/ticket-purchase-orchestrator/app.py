"""
Ticket Purchase Orchestrator.
Starts RabbitMQ queue topology and DLX consumer thread on startup.
"""
import os
import threading

from dotenv import load_dotenv
from flask import Flask, jsonify


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.update(JSON_SORT_KEYS=False, TESTING=False)
    if test_config:
        app.config.update(test_config)

    if not app.config.get("TESTING"):
        # Declare RabbitMQ topology
        try:
            from startup_queue_setup import bootstrap
            bootstrap()
        except Exception as exc:
            app.logger.warning("Queue setup failed: %s", exc)

        # Start DLX consumer in background thread
        from dlx_consumer import start_dlx_consumer
        t = threading.Thread(target=start_dlx_consumer, daemon=True, name="dlx-consumer")
        t.start()

    from routes import bp
    app.register_blueprint(bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "ticket-purchase-orchestrator"}), 200

    return app


app = create_app()
