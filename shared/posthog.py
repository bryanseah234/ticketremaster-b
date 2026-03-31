"""Shared PostHog initialization for backend services."""
import os
from typing import Optional, Dict, Any
from posthog import Posthog

_posthog_instance: Optional[Posthog] = None

def init_posthog() -> Optional[Posthog]:
    """Initialize PostHog client for backend event tracking."""
    global _posthog_instance
    
    api_key = os.getenv("POSTHOG_API_KEY")
    if not api_key:
        return None
    
    host = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")
    _posthog_instance = Posthog(
        api_key=api_key,
        host=host,
        disable_geoip=False
    )
    return _posthog_instance

def capture_event(
    distinct_id: str,
    event: str,
    properties: Optional[Dict[str, Any]] = None,
    timestamp: Optional[float] = None
) -> None:
    """Capture an event to PostHog."""
    if not _posthog_instance:
        return
    
    try:
        _posthog_instance.capture(
            distinct_id=distinct_id,
            event=event,
            properties=properties,
            timestamp=timestamp
        )
    except Exception as e:
        # Never let analytics break the app
        print(f"PostHog capture failed: {e}")

def identify_user(
    distinct_id: str,
    properties: Optional[Dict[str, Any]] = None
) -> None:
    """Identify a user in PostHog."""
    if not _posthog_instance:
        return
    
    try:
        _posthog_instance.identify(
            distinct_id=distinct_id,
            properties=properties
        )
    except Exception as e:
        print(f"PostHog identify failed: {e}")
