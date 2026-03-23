"""
Credit Orchestrator.
Handles credit balance enquiry, Stripe top-up initiation, and webhook processing.
The Stripe webhook endpoint is NOT protected by JWT — Stripe calls it directly.
"""
import os

from flask import Blueprint, jsonify, request

from middleware import require_auth
from service_client import call_credit_service, call_service

bp = Blueprint("credits", __name__)

STRIPE_WRAPPER     = os.environ.get("STRIPE_WRAPPER_URL",              "http://stripe-wrapper:5000")
CREDIT_TXN_SERVICE = os.environ.get("CREDIT_TRANSACTION_SERVICE_URL",  "http://credit-transaction-service:5000")


def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


# ── GET /credits/balance ──────────────────────────────────────────────────────

@bp.get("/credits/balance")
@require_auth
def get_balance():
    data, err = call_credit_service("GET", f"/credits/{request.user['userId']}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve balance.", 503)
    return jsonify({"data": data}), 200


# ── POST /credits/topup/initiate ──────────────────────────────────────────────

@bp.post("/credits/topup/initiate")
@require_auth
def initiate_topup():
    body = request.get_json(silent=True) or {}
    amount = body.get("amount")

    if amount is None or isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        return _error("VALIDATION_ERROR", "amount must be a positive number.", 400)

    result, err = call_service("POST", f"{STRIPE_WRAPPER}/stripe/create-payment-intent", json={
        "userId": request.user["userId"],
        "amount": int(amount),
    })
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not create payment intent.", 503)

    return jsonify({"data": {
        "clientSecret":    result["clientSecret"],
        "paymentIntentId": result["paymentIntentId"],
        "amount":          int(amount),
    }}), 200


# ── POST /credits/topup/webhook ───────────────────────────────────────────────

@bp.post("/credits/topup/webhook")
def stripe_webhook():
    """
    Called by Stripe (not the frontend).
    Stripe Wrapper verifies the signature and returns structured data.
    We handle idempotency and credit logic here.
    """
    payload   = request.get_data(cache=False, as_text=False)
    signature = request.headers.get("Stripe-Signature", "")

    result, err = call_service(
        "POST",
        f"{STRIPE_WRAPPER}/stripe/webhook",
        data=payload,
        headers={"Stripe-Signature": signature, "Content-Type": "application/json"},
    )
    if err:
        return _error("INTERNAL_ERROR", "Webhook processing failed.", 400)

    # Wrapper returns received=True for non-payment events — nothing to do
    if not result.get("userId"):
        return jsonify({"received": True}), 200

    user_id           = result["userId"]
    credits           = int(result["credits"])
    payment_intent_id = result["paymentIntentId"]

    # Idempotency — guard against duplicate Stripe deliveries
    existing, _ = call_service("GET", f"{CREDIT_TXN_SERVICE}/credit-transactions/reference/{payment_intent_id}")
    if existing:
        return jsonify({"received": True}), 200

    # Fetch current balance from OutSystems
    credit_data, err = call_credit_service("GET", f"/credits/{user_id}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve balance.", 503)

    new_balance = credit_data["creditBalance"] + credits

    # Update balance in OutSystems
    _, err = call_credit_service("PATCH", f"/credits/{user_id}", json={"creditBalance": new_balance})
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not update balance.", 503)

    # Log to Credit Transaction Service
    call_service("POST", f"{CREDIT_TXN_SERVICE}/credit-transactions", json={
        "userId":      user_id,
        "delta":       credits,
        "reason":      "topup",
        "referenceId": payment_intent_id,
    })

    return jsonify({"received": True}), 200


# ── GET /credits/transactions ─────────────────────────────────────────────────

@bp.get("/credits/transactions")
@require_auth
def get_transactions():
    params = {k: request.args[k] for k in ("page", "limit") if k in request.args}
    data, err = call_service("GET", f"{CREDIT_TXN_SERVICE}/credit-transactions/user/{request.user['userId']}", params=params)
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve transactions.", 503)
    return jsonify({"data": data}), 200
