import json
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone
from http import HTTPStatus

from dotenv import load_dotenv
from flasgger import Swagger
from flask import Flask, jsonify, request
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from werkzeug.exceptions import HTTPException

load_dotenv()

# Add shared directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))

# Validate secrets before any other initialization
import importlib.util

_shared_secrets_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared', 'secrets.py')
_shared_secrets_spec = importlib.util.spec_from_file_location('shared_secrets', _shared_secrets_path)
shared_secrets = importlib.util.module_from_spec(_shared_secrets_spec)
_shared_secrets_spec.loader.exec_module(shared_secrets)
shared_secrets.init_secrets(strict=os.getenv('APP_ENV') == 'production')

# Initialize Sentry for error tracking and performance monitoring
from sentry import init_sentry

init_sentry(service_name="user-service")

db = SQLAlchemy()
migrate = Migrate()


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
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JSON_SORT_KEYS=False,
        TESTING=False,
        VERBOSE_ERRORS=os.getenv("VERBOSE_ERRORS", "").lower() == "true",
    )

    if test_config:
        app.config.update(test_config)

    if "SQLALCHEMY_DATABASE_URI" not in app.config:
        validate_database_url = shared_secrets.validate_database_url
        database_url = os.getenv("USER_SERVICE_DATABASE_URL") or os.getenv(
            "DATABASE_URL"
        )
        database_url = validate_database_url(database_url, "user-service")
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url

    db.init_app(app)
    migrate.init_app(app, db)

    from models import User, PasswordResetToken  # noqa: F401
    from routes import bp as users_bp

    app.register_blueprint(users_bp)
    _register_error_handlers(app)

    @app.get("/health")
    def health_check():
        return jsonify({"status": "ok"}), 200

    Swagger(app, template={
        "info": {"title": "User Service", "version": "1.0.0"},
        "tags": [
            {"name": "Health"}, {"name": "Users"}, {"name": "Favorites"},
            {"name": "Auth"}, {"name": "Admin Users"},
        ],
    })

    return app


app = None
if os.getenv("USER_SERVICE_DATABASE_URL") or os.getenv("DATABASE_URL"):
    app = create_app()
