"""
Order Service — Flask application
Handles orders and transfers CRUD.
Phase 5: Implement all endpoints.
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
            "service": "order-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "database": "not_configured",
            },
        })

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=True)
