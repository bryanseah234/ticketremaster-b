"""
Shared JWT middleware for all TicketRemaster orchestrators.
Includes token blacklist checking for immediate revocation support.
"""
import os
from functools import wraps

import jwt
from flask import jsonify, request

# Import token blacklist from shared module
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
from token_blacklist import get_token_blacklist


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
            
            # Check if token is blacklisted
            token_blacklist = get_token_blacklist()
            jti = payload.get("jti")
            if jti and token_blacklist.is_blacklisted(jti):
                return _error("AUTH_TOKEN_REVOKED", "Token has been revoked. Please login again.", 401)
            
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
            
            # Check if token is blacklisted
            token_blacklist = get_token_blacklist()
            jti = payload.get("jti")
            if jti and token_blacklist.is_blacklisted(jti):
                return _error("AUTH_TOKEN_REVOKED", "Token has been revoked. Please login again.", 401)
            
            request.user = payload
        except jwt.ExpiredSignatureError:
            return _error("AUTH_TOKEN_EXPIRED", "Token has expired.", 401)
        except jwt.InvalidTokenError:
            return _error("AUTH_MISSING_TOKEN", "Token is invalid.", 401)
        if payload.get("role") not in ("staff", "admin"):
            return _error("AUTH_FORBIDDEN", "Staff or admin role required.", 403)
        return f(*args, **kwargs)
    return decorated


def revoke_token(token: str) -> bool:
    """
    Revoke a JWT token by adding it to the blacklist.
    
    Args:
        token: The JWT token string to revoke.
    
    Returns:
        True if successfully revoked, False otherwise.
    """
    try:
        # Decode without verification to get the payload
        payload = jwt.decode(token, options={"verify_signature": False})
        jti = payload.get("jti")
        exp = payload.get("exp")
        
        if not jti or not exp:
            return False
        
        token_blacklist = get_token_blacklist()
        return token_blacklist.blacklist_token(jti, exp, jti)
    except Exception:
        return False
