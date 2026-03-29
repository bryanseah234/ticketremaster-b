import time
import threading

from dotenv import load_dotenv
from flask import Flask, jsonify
from flasgger import Swagger

import sys
import signal
from shared.graceful_shutdown import setup_graceful_shutdown, create_cleanup_function


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.update(JSON_SORT_KEYS=False, TESTING=False)
    if test_config:
        app.config.update(test_config)

    app.config["SWAGGER"] = {
        "title": "Ticket Purchase Orchestrator",
        "uiversion": 3,
        "version": "1.0.0",
        "description": "Seat hold and purchase confirmation via gRPC + OutSystems credits.",
        "securityDefinitions": {
            "BearerAuth": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "Enter: Bearer <your_token>",
            }
        },
    }
    Swagger(app)

    if not app.config.get("TESTING"):
        for attempt in range(10):
            try:
                from startup_queue_setup import bootstrap
                bootstrap()
                app.logger.info("Queue setup complete")
                break
            except Exception as exc:
                app.logger.warning("Queue setup attempt %d failed: %s — retrying in 3s", attempt + 1, exc)
                time.sleep(3)

        from dlx_consumer import start_dlx_consumer
        t = threading.Thread(target=start_dlx_consumer, daemon=True, name="dlx-consumer")
        t.start()

    from routes import bp
    app.register_blueprint(bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "ticket-purchase-orchestrator"}), 200

    @app.get("/ready")
    def readiness():
        """Readiness probe endpoint - returns 503 during shutdown."""
        from shared.graceful_shutdown import is_shutting_down
        if is_shutting_down():
            return jsonify({"status": "shutting_down"}), 503
        return jsonify({"status": "ready"}), 200

    # Setup graceful shutdown
    cleanup = create_cleanup_function()
    setup_graceful_shutdown(app, cleanup_func=cleanup)

    return app


def main():
    """Main entry point with graceful shutdown support."""
    app = create_app()
    
    # Register signal handlers
    def shutdown_handler(signum, frame):
        import sys
        from shared.graceful_shutdown import graceful_shutdown
        graceful_shutdown(signum, frame, cleanup)
    
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    
    # Run the app
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    import os
    main()


app = create_app()
