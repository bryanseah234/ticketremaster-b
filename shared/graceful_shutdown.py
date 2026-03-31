"""
Graceful Shutdown Handler.

Provides graceful shutdown functionality for all Flask services.
Handles SIGTERM/SIGINT signals and ensures proper cleanup of resources.
Implements request draining to avoid dropping in-flight requests.
"""
import logging
import os
import signal
import sys
import time
import threading
from datetime import datetime, timezone
from typing import Optional, Callable
from flask import has_request_context

logger = logging.getLogger(__name__)

# Shutdown configuration
GRACEFUL_SHUTDOWN_TIMEOUT = int(os.environ.get("GRACEFUL_SHUTDOWN_TIMEOUT", "30"))
LB_DEREGISTRATION_DELAY = int(os.environ.get("LB_DEREGISTRATION_DELAY", "5"))
REQUEST_DRAIN_INTERVAL = float(os.environ.get("REQUEST_DRAIN_INTERVAL", "0.5"))

# Global shutdown flag
_is_shutting_down = False
_active_requests = 0
_request_lock = threading.Lock()
_shutdown_event = threading.Event()

# Request tracking middleware
_request_counter_lock = threading.Lock()


def set_shutting_down():
    """Set the global shutting down flag."""
    global _is_shutting_down
    _is_shutting_down = True
    _shutdown_event.set()


def is_shutting_down():
    """Check if the service is shutting down."""
    return _is_shutting_down


def get_active_requests():
    """Get the current count of active requests."""
    with _request_counter_lock:
        return _active_requests


def track_request_start():
    """Track the start of a request."""
    global _active_requests
    with _request_counter_lock:
        _active_requests += 1


def track_request_end():
    """Track the end of a request."""
    global _active_requests
    with _request_counter_lock:
        _active_requests = max(0, _active_requests - 1)


def graceful_shutdown(signum, frame, cleanup_func=None):
    """
    Handle graceful shutdown signal.
    
    Sequence:
    1. Set shutting down flag (stop accepting new requests)
    2. Wait for in-flight requests to complete (max GRACEFUL_SHUTDOWN_TIMEOUT)
    3. Cleanup resources (DB, Redis, RabbitMQ connections)
    4. Exit cleanly
    """
    logger.info("Received signal %d, initiating graceful shutdown...", signum)
    shutdown_start = datetime.now(timezone.utc)
    set_shutting_down()
    
    # Phase 1: Deregister from load balancer (if applicable)
    logger.info("Phase 1: Deregistering from load balancer (waiting %d seconds)...", 
                min(LB_DEREGISTRATION_DELAY, GRACEFUL_SHUTDOWN_TIMEOUT // 4))
    time.sleep(min(LB_DEREGISTRATION_DELAY, GRACEFUL_SHUTDOWN_TIMEOUT // 4))
    
    # Phase 2: Wait for in-flight requests with draining
    logger.info("Phase 2: Waiting for in-flight requests to complete (timeout: %d seconds)...", 
                GRACEFUL_SHUTDOWN_TIMEOUT * 3 // 4)
    wait_for_requests(timeout=GRACEFUL_SHUTDOWN_TIMEOUT * 3 // 4)
    
    # Phase 3: Cleanup resources
    logger.info("Phase 3: Cleaning up resources...")
    if cleanup_func:
        try:
            cleanup_func()
        except Exception as exc:
            logger.error("Error during resource cleanup: %s", exc)
    
    shutdown_duration = (datetime.now(timezone.utc) - shutdown_start).total_seconds()
    logger.info("Graceful shutdown complete (duration: %.2fs). Exiting...", shutdown_duration)
    sys.exit(0)


def wait_for_requests(timeout):
    """
    Wait for in-flight requests to complete with draining.
    Monitors active request count and waits until all are complete or timeout.
    """
    start_time = time.time()
    last_count = get_active_requests()
    
    while time.time() - start_time < timeout:
        current_count = get_active_requests()
        
        if current_count == 0:
            logger.info("All in-flight requests completed")
            return
        
        if current_count != last_count:
            logger.info("Waiting for %d in-flight requests to complete...", current_count)
            last_count = current_count
        
        time.sleep(REQUEST_DRAIN_INTERVAL)
    
    # Timeout reached
    remaining = get_active_requests()
    if remaining > 0:
        logger.warning("Shutdown timeout reached with %d requests still active. Forcing exit.", remaining)
    else:
        logger.info("Request draining completed within timeout")


def setup_graceful_shutdown(app, cleanup_func=None):
    """
    Setup graceful shutdown handlers for a Flask app.
    
    Args:
        app: Flask application instance
        cleanup_func: Optional function to call for resource cleanup
    """
    def shutdown_handler(signum, frame):
        graceful_shutdown(signum, frame, cleanup_func)
    
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    
    logger.info("Graceful shutdown handlers registered")


def shutdown_hook(func):
    """
    Decorator to register a function as a shutdown hook.
    Multiple hooks can be registered and will be called in order.
    """
    if not hasattr(shutdown_hook, 'hooks'):
        shutdown_hook.hooks = []
    shutdown_hook.hooks.append(func)
    return func


def run_shutdown_hooks():
    """Execute all registered shutdown hooks."""
    if hasattr(shutdown_hook, 'hooks'):
        for hook in shutdown_hook.hooks:
            try:
                hook()
            except Exception as exc:
                logger.error("Error in shutdown hook %s: %s", hook.__name__, exc)


def create_cleanup_function(db=None, redis_client=None, rabbitmq_connection=None):
    """
    Create a cleanup function that closes all resources.
    
    Args:
        db: SQLAlchemy database instance
        redis_client: Redis client instance
        rabbitmq_connection: Pika connection instance
    
    Returns:
        Function that cleans up all provided resources
    """
    def cleanup():
        # Close database connections
        if db is not None:
            try:
                db.session.close_all()
                db.engine.dispose()
                logger.info("Database connections closed")
            except Exception as exc:
                logger.error("Error closing database connections: %s", exc)
        
        # Close Redis connection
        if redis_client is not None:
            try:
                redis_client.close()
                logger.info("Redis connection closed")
            except Exception as exc:
                logger.error("Error closing Redis connection: %s", exc)
        
        # Close RabbitMQ connection
        if rabbitmq_connection is not None:
            try:
                if not rabbitmq_connection.is_closed:
                    rabbitmq_connection.close()
                logger.info("RabbitMQ connection closed")
            except Exception as exc:
                logger.error("Error closing RabbitMQ connection: %s", exc)
        
        # Run any registered shutdown hooks
        run_shutdown_hooks()
    
    return cleanup


def register_request_tracking_middleware(app):
    """
    Register middleware to track active requests for graceful shutdown.
    
    Args:
        app: Flask application instance
    """
    @app.before_request
    def before_request():
        track_request_start()
    
    @app.teardown_request
    def teardown_request(exception):
        track_request_end()
    
    logger.info("Request tracking middleware registered")
