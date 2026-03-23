"""
Shared JWT middleware for all TicketRemaster orchestrators.
"""
import os
from functools import wraps

import jwt
from flask import jsonify, request


def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return _error("AUTH_MISSING_TOKEN", "Authorization header missing or malformed.", 401)
        token = auth[len("Bearer "):]
        try:
            payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
            request.user = payload
        except jwt.ExpiredSignatureError:
            return _error("AUTH_TOKEN_EXPIRED", "Token has expired.", 401)
        except jwt.InvalidTokenError:
            return _error("AUTH_MISSING_TOKEN", "Token is invalid.", 401)
        return f(*args, **kwargs)
    return decorated


def require_staff(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return _error("AUTH_MISSING_TOKEN", "Authorization header missing or malformed.", 401)
        token = auth[len("Bearer "):]
        try:
            payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
            request.user = payload
        except jwt.ExpiredSignatureError:
            return _error("AUTH_TOKEN_EXPIRED", "Token has expired.", 401)
        except jwt.InvalidTokenError:
            return _error("AUTH_MISSING_TOKEN", "Token is invalid.", 401)
        if payload.get("role") not in ("staff", "admin"):
            return _error("AUTH_FORBIDDEN", "Staff or admin role required.", 403)
        return f(*args, **kwargs)
    return decorated
