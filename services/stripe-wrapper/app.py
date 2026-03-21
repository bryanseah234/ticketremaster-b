import json
import os
import traceback
import uuid
from datetime import datetime, timezone
from http import HTTPStatus

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

load_dotenv()


def _http_error_code(status_code):
    try:
        return HTTPStatus(status_code).name
    except ValueError:
        return "HTTP_ERROR"


def _build_error_payload(status_code, code, message, exc=None):
    details = {
        "method": request.method,
        "path": request.path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "resolution": "Check error.code, request payload, and service logs using traceId.",
    }
    if exc is not None:
        details["exceptionType"] = type(exc).__name__
        details["exceptionMessage"] = str(exc)
        details["stackTrace"] = traceback.format_exception(
            type(exc), exc, exc.__traceback__
        )
    return {
        "error": {
            "code": code,
            "message": message,
            "status": status_code,
            "traceId": str(uuid.uuid4()),
            "details": details,
        }
    }


def _register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http_exception(exc):
        status_code = exc.code or 500
        payload = _build_error_payload(
            status_code=status_code,
            code=_http_error_code(status_code),
            message=exc.description or str(exc),
            exc=exc if app.config.get("VERBOSE_ERRORS", True) else None,
        )
        return jsonify(payload), status_code

    @app.errorhandler(Exception)
    def handle_unhandled_exception(exc):
        payload = _build_error_payload(
            status_code=500,
            code="INTERNAL_ERROR",
            message="Unhandled internal server error.",
            exc=exc if app.config.get("VERBOSE_ERRORS", True) else None,
        )
        return jsonify(payload), 500

    @app.after_request
    def enrich_error_payload(response):
        if response.status_code < 400 or not response.is_json:
            return response
        payload = response.get_json(silent=True)
        if not isinstance(payload, dict):
            return response
        error = payload.get("error")
        if not isinstance(error, dict):
            return response
        error.setdefault("status", response.status_code)
        error.setdefault("traceId", str(uuid.uuid4()))
        details = error.get("details")
        if not isinstance(details, dict):
            details = {}
        details.setdefault("method", request.method)
        details.setdefault("path", request.path)
        details.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        details.setdefault(
            "resolution",
            "Check error.code, request payload, and service logs using traceId.",
        )
        error["details"] = details
        payload["error"] = error
        response.set_data(json.dumps(payload))
        response.mimetype = "application/json"
        return response


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        JSON_SORT_KEYS=False,
        TESTING=False,
        VERBOSE_ERRORS=True,
    )

    if test_config:
        app.config.update(test_config)

    if "STRIPE_SECRET_KEY" not in app.config:
        stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")
        if not stripe_secret_key:
            raise RuntimeError("STRIPE_SECRET_KEY must be set for stripe-wrapper.")
        app.config["STRIPE_SECRET_KEY"] = stripe_secret_key

    if "STRIPE_WEBHOOK_SECRET" not in app.config:
        stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        if not stripe_webhook_secret:
            raise RuntimeError("STRIPE_WEBHOOK_SECRET must be set for stripe-wrapper.")
        app.config["STRIPE_WEBHOOK_SECRET"] = stripe_webhook_secret

    from routes import bp as stripe_wrapper_bp

    app.register_blueprint(stripe_wrapper_bp)
    _register_error_handlers(app)

    @app.get("/health")
    def health_check():
        return jsonify({"status": "ok"}), 200

    return app


app = None
if os.getenv("STRIPE_SECRET_KEY") and os.getenv("STRIPE_WEBHOOK_SECRET"):
    app = create_app()
