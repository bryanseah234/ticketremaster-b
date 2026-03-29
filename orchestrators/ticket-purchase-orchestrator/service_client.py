"""
Shared HTTP helpers for all TicketRemaster orchestrators.
Implements timeout configuration, circuit breaker pattern, and retry logic.
"""
import logging
import os
import random
import time
from threading import Lock

import requests

logger = logging.getLogger(__name__)

# Timeout configuration (in seconds)
CONNECT_TIMEOUT = int(os.environ.get("CONNECT_TIMEOUT", "2"))
READ_TIMEOUT = int(os.environ.get("READ_TIMEOUT", "5"))
TOTAL_TIMEOUT = int(os.environ.get("TOTAL_TIMEOUT", "10"))
DEFAULT_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

# Circuit breaker configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.environ.get("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3"))
CIRCUIT_BREAKER_RECOVERY_SECONDS = int(os.environ.get("CIRCUIT_BREAKER_RECOVERY_SECONDS", "30"))
CIRCUIT_BREAKER_HALF_OPEN_MAX_REQUESTS = int(os.environ.get("CIRCUIT_BREAKER_HALF_OPEN_MAX_REQUESTS", "1"))

# Retry configuration
MAX_RETRIES = int(os.environ.get("HTTP_MAX_RETRIES", "2"))
RETRY_BACKOFF_FACTOR = float(os.environ.get("HTTP_RETRY_BACKOFF_FACTOR", "0.5"))


class CircuitBreaker:
    """
    Circuit breaker implementation for service calls.
    States: CLOSED (normal), OPEN (failing), HALF_OPEN (testing)
    """
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(self, name, failure_threshold=CIRCUIT_BREAKER_FAILURE_THRESHOLD,
                 recovery_timeout=CIRCUIT_BREAKER_RECOVERY_SECONDS):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitBreaker.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_successes = 0
        self._lock = Lock()
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == CircuitBreaker.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreaker.HALF_OPEN
                    self.half_open_successes = 0
                    logger.info("Circuit breaker %s entering half-open state", self.name)
                else:
                    raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self):
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call."""
        with self._lock:
            if self.state == CircuitBreaker.HALF_OPEN:
                self.half_open_successes += 1
                if self.half_open_successes >= CIRCUIT_BREAKER_HALF_OPEN_MAX_REQUESTS:
                    self.state = CircuitBreaker.CLOSED
                    self.failure_count = 0
                    logger.info("Circuit breaker %s closed after successful test", self.name)
            else:
                self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreaker.OPEN
                logger.warning("Circuit breaker %s opened after %d failures", self.name, self.failure_count)


# Global circuit breakers for each service
_circuit_breakers = {}
_cb_lock = Lock()


def _get_circuit_breaker(service_name):
    """Get or create circuit breaker for a service."""
    with _cb_lock:
        if service_name not in _circuit_breakers:
            _circuit_breakers[service_name] = CircuitBreaker(service_name)
        return _circuit_breakers[service_name]


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# Configurable timeout for OutSystems calls (default 5 seconds)
OUTSYSTEMS_TIMEOUT = int(os.environ.get("OUTSYSTEMS_TIMEOUT_SECONDS", "5"))


def call_service(method, url, **kwargs):
    """
    Call an internal service with timeout, retries, and circuit breaker.
    Returns (response_json, None) on success.
    Returns (None, error_code_str) on failure.
    Propagates the downstream error code where possible.
    """
    # Set timeout if not provided
    if "timeout" not in kwargs:
        kwargs["timeout"] = DEFAULT_TIMEOUT
    
    # Extract service name for circuit breaker (from URL)
    service_name = url.split("://")[1].split(":")[0] if "://" in url else "unknown"
    
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            # Apply circuit breaker
            cb = _get_circuit_breaker(service_name)
            
            def make_request():
                resp = requests.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp.json()
            
            result = cb.call(make_request)
            return result, None
            
        except CircuitBreakerOpenError:
            logger.warning("Circuit breaker open for service %s", service_name)
            return None, "SERVICE_UNAVAILABLE"
            
        except requests.exceptions.Timeout as exc:
            last_error = exc
            logger.warning("Timeout calling %s (attempt %d/%d): %s", url, attempt + 1, MAX_RETRIES + 1, exc)
            if attempt < MAX_RETRIES:
                # Exponential backoff with jitter
                delay = RETRY_BACKOFF_FACTOR * (2 ** attempt) + random.uniform(0, 0.1)
                time.sleep(delay)
            
        except requests.exceptions.ConnectionError as exc:
            last_error = exc
            logger.warning("Connection error calling %s (attempt %d/%d): %s", url, attempt + 1, MAX_RETRIES + 1, exc)
            if attempt < MAX_RETRIES:
                delay = RETRY_BACKOFF_FACTOR * (2 ** attempt) + random.uniform(0, 0.1)
                time.sleep(delay)
            
        except requests.exceptions.HTTPError as exc:
            # Don't retry server errors (5xx) but do retry client errors (4xx)
            if exc.response and exc.response.status_code >= 500:
                last_error = exc
                logger.warning("Server error calling %s (attempt %d/%d): %s", url, attempt + 1, MAX_RETRIES + 1, exc)
                if attempt < MAX_RETRIES:
                    delay = RETRY_BACKOFF_FACTOR * (2 ** attempt) + random.uniform(0, 0.1)
                    time.sleep(delay)
            else:
                # Client error - don't retry
                try:
                    body = exc.response.json()
                    code = body.get("error", {}).get("code", "SERVICE_UNAVAILABLE")
                except Exception:
                    code = "SERVICE_UNAVAILABLE"
                return None, code
    
    # All retries exhausted
    logger.error("All retries exhausted for %s", url)
    return None, "SERVICE_UNAVAILABLE"


def call_credit_service(method, path, **kwargs):
    """
    Call the OutSystems Credit Service.
    Automatically injects the OUTSYSTEMS_API_KEY header.
    Uses configurable timeout from OUTSYSTEMS_TIMEOUT_SECONDS env var.
    """
    headers = kwargs.pop("headers", {})
    headers["X-API-KEY"] = os.environ["OUTSYSTEMS_API_KEY"]
    base = os.environ["CREDIT_SERVICE_URL"].rstrip("/")
    # Apply OutSystems-specific timeout if not already set
    kwargs.setdefault("timeout", OUTSYSTEMS_TIMEOUT)
    return call_service(method, f"{base}{path}", headers=headers, **kwargs)
