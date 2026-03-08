import os
import json
import logging
import uuid
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager
from datetime import datetime, timezone

# Structured JSON logging
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": "orchestrator-service",
            "correlation_id": getattr(record, "correlation_id", None),
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

from flask import has_request_context

class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        if has_request_context():
            record.correlation_id = getattr(request, "correlation_id", None)
        else:
            record.correlation_id = None
        return True

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
handler.addFilter(CorrelationIdFilter())
logger = logging.getLogger("orchestrator")
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def create_app():
    app = Flask(__name__)
    
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET', 'test-secret')
    app.config['JWT_IDENTITY_CLAIM'] = 'sub' # Just in case
    jwt = JWTManager(app)

    @app.before_request
    def set_correlation_id():
        corr_id = request.headers.get("X-Correlation-ID")
        request.correlation_id = corr_id if corr_id else str(uuid.uuid4())

    @app.after_request
    def add_correlation_header(response):
        if hasattr(request, "correlation_id"):
            response.headers["X-Correlation-ID"] = request.correlation_id
        return response

    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred."
        }), 500

    @app.route("/health")
    def health():
        return jsonify({
            "status": "healthy",
            "service": "orchestrator-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    from src.routes.purchase_routes import purchase_bp
    from src.routes.transfer_routes import transfer_bp
    from src.routes.verification_routes import verification_bp
    from src.routes.ticket_routes import ticket_bp
    from src.routes.admin_routes import admin_bp
    from src.routes.marketplace_routes import marketplace_bp
    
    app.register_blueprint(purchase_bp, url_prefix='/api')
    app.register_blueprint(transfer_bp, url_prefix='/api')
    app.register_blueprint(verification_bp, url_prefix='/api')
    app.register_blueprint(ticket_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(marketplace_bp, url_prefix='/api')

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5003, debug=True)
