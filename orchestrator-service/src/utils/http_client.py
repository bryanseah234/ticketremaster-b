import os
import requests
import uuid
from flask import request

class ServiceClient:
    def __init__(self, service_url: str):
        self.base_url = service_url

    def _get_headers(self, headers=None):
        req_headers = headers or {}
        try:
            correlation_id = request.headers.get("X-Correlation-ID") or getattr(request, "correlation_id", str(uuid.uuid4()))
            req_headers["X-Correlation-ID"] = correlation_id
        except RuntimeError:
            pass # Outside request context
        return req_headers

    def get(self, path: str, headers=None, **kwargs):
        return requests.get(f"{self.base_url}{path}", headers=self._get_headers(headers), **kwargs)

    def post(self, path: str, json=None, headers=None, **kwargs):
        return requests.post(f"{self.base_url}{path}", json=json, headers=self._get_headers(headers), **kwargs)

    def patch(self, path: str, json=None, headers=None, **kwargs):
        return requests.patch(f"{self.base_url}{path}", json=json, headers=self._get_headers(headers), **kwargs)

user_service = ServiceClient(os.environ.get("USER_SERVICE_URL", "http://user-service:5000"))
order_service = ServiceClient(os.environ.get("ORDER_SERVICE_URL", "http://order-service:5001"))
event_service = ServiceClient(os.environ.get("EVENT_SERVICE_URL", "http://event-service:5002"))
inventory_service_http = ServiceClient(os.environ.get("INVENTORY_SERVICE_HTTP_URL", "http://inventory-service:8080"))
