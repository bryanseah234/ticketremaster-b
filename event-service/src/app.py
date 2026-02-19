"""
Event Service — Flask application
Handles event listing and detail with seat availability.
Phase 3: Implement all endpoints (simplest service, start here).
"""

from flask import Flask, jsonify
from datetime import datetime, timezone


def create_app():
    app = Flask(__name__)

    # --- Health check ---------------------------------------------------
    @app.route("/health")
    def health():
        return jsonify({
            "status": "healthy",
            "service": "event-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "database": "not_configured",
            },
        })

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5002, debug=True)
