"""
Orchestrator Service — Saga Manager
Coordinates all multi-step flows (purchase, transfer, verification).
All external traffic flows through Kong → here → atomic services.
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
            "service": "orchestrator-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "inventory": "not_configured",
                "user": "not_configured",
                "order": "not_configured",
                "event": "not_configured",
                "rabbitmq": "not_configured",
            },
        })

    # --- Register route blueprints (Phase 7) ----------------------------
    # from src.routes.purchase_routes import purchase_bp
    # from src.routes.transfer_routes import transfer_bp
    # from src.routes.verification_routes import verification_bp
    # app.register_blueprint(purchase_bp)
    # app.register_blueprint(transfer_bp)
    # app.register_blueprint(verification_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5003, debug=True)
