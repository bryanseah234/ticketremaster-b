"""Tests for credit-orchestrator."""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt


def _token(user_id="usr_001", role="user"):
    return jwt.encode(
        {"userId": user_id, "email": "t@t.com", "role": role,
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        os.environ["JWT_SECRET"], algorithm="HS256",
    )


def _auth(user_id="usr_001"):
    return {"Authorization": f"Bearer {_token(user_id)}"}


def test_health(client):
    assert client.get("/health").status_code == 200


# ── GET /credits/balance ──────────────────────────────────────────────────────

@patch("routes.call_credit_service")
def test_balance_success(mock_credit, client):
    mock_credit.return_value = ({"creditBalance": 100.0}, None)
    res = client.get("/credits/balance", headers=_auth())
    assert res.status_code == 200
    assert res.get_json()["data"]["creditBalance"] == 100.0


def test_balance_no_auth(client):
    assert client.get("/credits/balance").status_code == 401


@patch("routes.call_credit_service")
def test_balance_outsystems_down(mock_credit, client):
    mock_credit.return_value = (None, "SERVICE_UNAVAILABLE")
    assert client.get("/credits/balance", headers=_auth()).status_code == 503


# ── POST /credits/topup/initiate ──────────────────────────────────────────────

@patch("routes.call_service")
def test_topup_initiate_success(mock_svc, client):
    mock_svc.return_value = ({"clientSecret": "pi_secret", "paymentIntentId": "pi_001", "amount": 50}, None)
    res = client.post("/credits/topup/initiate", json={"amount": 50}, headers=_auth())
    assert res.status_code == 200
    assert res.get_json()["data"]["clientSecret"] == "pi_secret"


def test_topup_initiate_invalid_amount(client):
    res = client.post("/credits/topup/initiate", json={"amount": -5}, headers=_auth())
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_topup_initiate_zero(client):
    assert client.post("/credits/topup/initiate", json={"amount": 0}, headers=_auth()).status_code == 400


def test_topup_initiate_no_auth(client):
    assert client.post("/credits/topup/initiate", json={"amount": 50}).status_code == 401


# ── POST /credits/topup/webhook ───────────────────────────────────────────────

@patch("routes.call_credit_service")
@patch("routes.call_service")
def test_webhook_success(mock_svc, mock_credit, client):
    mock_svc.side_effect = [
        ({"userId": "usr_001", "credits": "50", "paymentIntentId": "pi_001"}, None),  # wrapper verify
        (None, "TRANSACTION_NOT_FOUND"),   # idempotency check — not found
        (None, None),                      # log transaction
    ]
    mock_credit.side_effect = [
        ({"creditBalance": 100.0}, None),   # GET balance
        ({}, None),                         # PATCH balance
    ]
    res = client.post("/credits/topup/webhook",
                      data=b'{}', headers={"Stripe-Signature": "sig", "Content-Type": "application/json"})
    assert res.status_code == 200


@patch("routes.call_service")
def test_webhook_invalid_signature(mock_svc, client):
    mock_svc.return_value = (None, "INVALID_SIGNATURE")
    res = client.post("/credits/topup/webhook",
                      data=b'{}', headers={"Stripe-Signature": "bad", "Content-Type": "application/json"})
    assert res.status_code == 400


@patch("routes.call_credit_service")
@patch("routes.call_service")
def test_webhook_idempotent(mock_svc, mock_credit, client):
    """Duplicate webhook must not credit twice."""
    mock_svc.side_effect = [
        ({"userId": "usr_001", "credits": "50", "paymentIntentId": "pi_001"}, None),
        ({"txnId": "existing"}, None),  # idempotency hit
    ]
    res = client.post("/credits/topup/webhook",
                      data=b'{}', headers={"Stripe-Signature": "sig", "Content-Type": "application/json"})
    assert res.status_code == 200
    mock_credit.assert_not_called()  # balance must not be touched


# ── GET /credits/transactions ─────────────────────────────────────────────────

@patch("routes.call_service")
def test_transactions_success(mock_svc, client):
    mock_svc.return_value = ({
        "transactions": [{"txnId": "t1", "delta": 50.0, "reason": "topup"}],
        "pagination": {"page": 1, "total": 1},
    }, None)
    res = client.get("/credits/transactions", headers=_auth())
    assert res.status_code == 200
    assert len(res.get_json()["data"]["transactions"]) == 1


def test_transactions_no_auth(client):
    assert client.get("/credits/transactions").status_code == 401
