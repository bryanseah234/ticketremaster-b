"""
Shared HTTP helpers for all TicketRemaster orchestrators.
"""
import os

import requests


def call_service(method, url, **kwargs):
    """
    Call an internal service.
    Returns (response_json, None) on success.
    Returns (None, error_code_str) on failure.
    Propagates the downstream error code where possible.
    """
    try:
        kwargs.setdefault("timeout", 5)
        resp = requests.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.Timeout:
        return None, "SERVICE_UNAVAILABLE"
    except requests.exceptions.ConnectionError:
        return None, "SERVICE_UNAVAILABLE"
    except requests.exceptions.HTTPError as exc:
        try:
            body = exc.response.json()
            code = body.get("error", {}).get("code", "SERVICE_UNAVAILABLE")
        except Exception:
            code = "SERVICE_UNAVAILABLE"
        return None, code


def call_credit_service(method, path, **kwargs):
    """
    Call the OutSystems Credit Service.
    Automatically injects the OUTSYSTEMS_API_KEY header.
    """
    headers = kwargs.pop("headers", {})
    headers["X-API-Key"] = os.environ["OUTSYSTEMS_API_KEY"]
    base = os.environ["CREDIT_SERVICE_URL"].rstrip("/")
    return call_service(method, f"{base}{path}", headers=headers, **kwargs)
