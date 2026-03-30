"""
Shared Sentry initialization for Flask microservices.
Provides centralized error tracking, performance monitoring, and logging.
"""
import os
from typing import Optional

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from flask import Flask


def init_sentry(
    app: Optional[Flask] = None,
    service_name: Optional[str] = None,
    traces_sample_rate: Optional[float] = None,
) -> None:
    """
    Initialize Sentry SDK for a Flask microservice.
    
    Args:
        app: Flask application instance (optional)
        service_name: Service name for Sentry releases (optional)
        traces_sample_rate: Sample rate for performance tracing (0.0-1.0)
    """
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        # Sentry not configured, skip initialization
        return

    environment = os.getenv("SENTRY_ENVIRONMENT", "development")
    
    if traces_sample_rate is None:
        traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

    release = None
    if service_name:
        app_version = os.getenv("APP_VERSION", "dev")
        release = f"{service_name}@{app_version}"

    # Configure logging integration to not override Flask's logging
    logging_integration = LoggingIntegration(
        level=None,        # Capture info and above as breadcrumbs
        event_level=None,  # No automatic log-to-event conversion
    )

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        integrations=[
            FlaskIntegration(),
            logging_integration,
        ],
        # Performance monitoring
        traces_sample_rate=traces_sample_rate,
        traces_sampler=_traces_sampler,
        # Profiling (optional, for performance analysis)
        profiles_sample_rate=0.1,
        profile_lifecycle="trace",
        # Error monitoring
        send_default_pii=True,
        # Logs
        enable_logs=True,
        # Breadcrumbs
        max_breadcrumbs=100,
        # Attach stacktrace to events
        attach_stacktrace=True,
    )


def _traces_sampler(sampling_context):
    """
    Custom sampler to control which transactions are sent to Sentry.
    Can be customized per service or route.
    """
    # Health check endpoints - don't sample
    if sampling_context.get("name") == "health_check":
        return 0.0
    
    # Static files - don't sample
    if sampling_context.get("name") == "static":
        return 0.0
    
    # Default sample rate from config
    return float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))


def capture_exception(error: Exception, context: Optional[dict] = None) -> Optional[str]:
    """
    Capture an exception with additional context.
    
    Args:
        error: The exception to capture
        context: Optional context dictionary
        
    Returns:
        Event ID if sent, None otherwise
    """
    if context:
        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_context(key, value)
            return sentry_sdk.capture_exception(error)
    return sentry_sdk.capture_exception(error)


def set_user(user_id: Optional[str] = None, email: Optional[str] = None, **kwargs) -> None:
    """
    Set the current user context for error tracking.
    
    Args:
        user_id: User identifier
        email: User email address
        **kwargs: Additional user attributes
    """
    user_data = {}
    if user_id:
        user_data["id"] = user_id
    if email:
        user_data["email"] = email
    user_data.update(kwargs)
    sentry_sdk.set_user(user_data)


def add_breadcrumb(message: str, category: str = "default", level: str = "info", **kwargs) -> None:
    """
    Add a breadcrumb for debugging context.
    
    Args:
        message: Breadcrumb message
        category: Category for grouping (e.g., "auth", "query", "http")
        level: Severity level (debug, info, warning, error)
        **kwargs: Additional data
    """
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=kwargs,
    )
