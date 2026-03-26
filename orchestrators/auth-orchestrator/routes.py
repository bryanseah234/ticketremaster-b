import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import Blueprint, jsonify, request

from middleware import require_auth
from service_client import call_credit_service, call_service

bp = Blueprint("auth", __name__)

USER_SERVICE = os.environ.get("USER_SERVICE_URL", "http://user-service:5000")
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))


def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def _generate_token(user):
    payload = {
        "userId": user["userId"],
        "email": user["email"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    # Staff users carry venueId so ticket-verification-orchestrator
    # can check venue without an extra lookup.
    if user.get("role") == "staff" and user.get("venueId"):
        payload["venueId"] = user["venueId"]
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


# ── POST /auth/register ──────────────────────────────────────────────────────

@bp.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    required = ("email", "password", "phoneNumber")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return _error("VALIDATION_ERROR", f"Missing required fields: {', '.join(missing)}", 400)

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(data["password"].encode(), salt).decode()

    user_data, err = call_service("POST", f"{USER_SERVICE}/users", json={
        "email": data["email"],
        "password": hashed,
        "salt": salt.decode(),
        "role": data["role"],
        "phoneNumber": data["phoneNumber"],
        "venueId": data.get("venueId"),
    })
    if err == "EMAIL_ALREADY_EXISTS":
        return _error("EMAIL_ALREADY_EXISTS", "Email is already registered.", 409)
    if err:
        return _error(err, "Could not create user account.", 400)

    # Initialise credit balance in OutSystems
    _, credit_err = call_credit_service("POST", "/credits", json={"userId": user_data["userId"]})
    if credit_err:
        # Compensating action — delete the user we just created
        call_service("DELETE", f"{USER_SERVICE}/users/{user_data['userId']}")
        return _error("INTERNAL_ERROR", "Could not initialise account. Please try again.", 500)

    return jsonify({"data": {
        "userId": user_data["userId"],
        "email": user_data["email"],
        "role": user_data["role"],
        "createdAt": user_data["createdAt"],
    }}), 201


# ── POST /auth/login ─────────────────────────────────────────────────────────

@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    if not data.get("email") or not data.get("password"):
        return _error("VALIDATION_ERROR", "email and password are required.", 400)

    user_data, err = call_service("GET", f"{USER_SERVICE}/users/by-email/{data['email']}")
    if err:
        # Return the same error for not-found and wrong password to avoid enumeration
        return _error("AUTH_INVALID_CREDENTIALS", "Invalid email or password.", 401)

    if user_data.get("isFlagged"):
        return _error("AUTH_FORBIDDEN", "Account has been suspended.", 403)

    if not bcrypt.checkpw(data["password"].encode(), user_data["password"].encode()):
        return _error("AUTH_INVALID_CREDENTIALS", "Invalid email or password.", 401)

    token = _generate_token(user_data)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)).isoformat()

    return jsonify({"data": {
        "token": token,
        "expiresAt": expires_at,
        "user": {
            "userId": user_data["userId"],
            "email": user_data["email"],
            "role": user_data["role"],
        },
    }}), 200


# ── GET /auth/me ─────────────────────────────────────────────────────────────

@bp.get("/auth/me")
@require_auth
def me():
    user_data, err = call_service("GET", f"{USER_SERVICE}/users/{request.user['userId']}")
    if err:
        return _error("USER_NOT_FOUND", "User not found.", 404)

    return jsonify({"data": {
        "userId": user_data["userId"],
        "email": user_data["email"],
        "phoneNumber": user_data.get("phoneNumber"),
        "role": user_data["role"],
        "isFlagged": user_data.get("isFlagged", False),
        "createdAt": user_data["createdAt"],
    }}), 200
