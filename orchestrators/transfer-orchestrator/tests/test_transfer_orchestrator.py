"""Tests for transfer-orchestrator."""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt


def _token(user_id="usr_buyer", role="user"):
    return jwt.encode(
        {"userId": user_id, "email": f"{user_id}@t.com", "role": role,
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        os.environ["JWT_SECRET"], algorithm="HS256",
    )


def _auth(user_id):
    return {"Authorization": f"Bearer {_token(user_id)}"}


BUYER  = "usr_buyer"
SELLER = "usr_seller"

MOCK_LISTING = {
    "listingId": "lst_001", "ticketId": "tkt_001",
    "sellerId": SELLER, "price": 80.0, "status": "active",
}
MOCK_TRANSFER = {
    "transferId": "txr_001", "listingId": "lst_001",
    "buyerId": BUYER, "sellerId": SELLER,
    "status": "pending_buyer_otp", "creditAmount": 80.0,
    "buyerOtpVerified": False, "sellerOtpVerified": False,
    "buyerVerificationSid": "VE_buyer", "sellerVerificationSid": None,
    "completedAt": None,
}
MOCK_BUYER_USER  = {"userId": BUYER,  "phoneNumber": "+6591111111"}
MOCK_SELLER_USER = {"userId": SELLER, "phoneNumber": "+6592222222"}


def test_health(client):
    assert client.get("/health").status_code == 200


# ── POST /transfer/initiate ───────────────────────────────────────────────────

@patch("routes._publish_seller_notification")
@patch("routes.call_service")
@patch("routes.call_credit_service")
def test_initiate_success(mock_credit, mock_svc, mock_notify, client):
    mock_credit.return_value = ({"creditBalance": 200.0}, None)
    mock_svc.side_effect = [
        (MOCK_LISTING, None),
        ({"transferId": "txr_001", "status": "pending_seller_acceptance"}, None),
    ]
    res = client.post("/transfer/initiate", json={"listingId": "lst_001"}, headers=_auth(BUYER))
    assert res.status_code == 201
    assert res.get_json()["data"]["status"] == "pending_seller_acceptance"
    mock_notify.assert_called_once_with("txr_001", SELLER)


@patch("routes.call_service")
@patch("routes.call_credit_service")
def test_initiate_own_listing(mock_credit, mock_svc, client):
    listing = {**MOCK_LISTING, "sellerId": BUYER}
    mock_svc.return_value = (listing, None)
    res = client.post("/transfer/initiate", json={"listingId": "lst_001"}, headers=_auth(BUYER))
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "AUTH_FORBIDDEN"


@patch("routes.call_service")
@patch("routes.call_credit_service")
def test_initiate_insufficient_credits(mock_credit, mock_svc, client):
    mock_svc.return_value = (MOCK_LISTING, None)
    mock_credit.return_value = ({"creditBalance": 5.0}, None)
    res = client.post("/transfer/initiate", json={"listingId": "lst_001"}, headers=_auth(BUYER))
    assert res.status_code == 402
    assert res.get_json()["error"]["code"] == "INSUFFICIENT_CREDITS"


@patch("routes.call_service")
@patch("routes.call_credit_service")
def test_initiate_listing_not_active(mock_credit, mock_svc, client):
    listing = {**MOCK_LISTING, "status": "completed"}
    mock_svc.return_value = (listing, None)
    res = client.post("/transfer/initiate", json={"listingId": "lst_001"}, headers=_auth(BUYER))
    assert res.status_code == 400


def test_initiate_no_listing_id(client):
    res = client.post("/transfer/initiate", json={}, headers=_auth(BUYER))
    assert res.status_code == 400


# ── POST /transfer/<id>/buyer-verify ─────────────────────────────────────────

@patch("routes.call_service")
def test_buyer_verify_success(mock_svc, client):
    mock_svc.side_effect = [
        (MOCK_TRANSFER, None),
        ({"verified": True}, None),
        (MOCK_SELLER_USER, None),
        ({"sid": "VE_seller"}, None),
        (None, None),
    ]
    res = client.post("/transfer/txr_001/buyer-verify",
                      json={"otp": "123456"}, headers=_auth(BUYER))
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "pending_seller_otp"


@patch("routes.call_service")
def test_buyer_verify_wrong_otp(mock_svc, client):
    mock_svc.side_effect = [
        (MOCK_TRANSFER, None),
        ({"verified": False}, None),
    ]
    res = client.post("/transfer/txr_001/buyer-verify",
                      json={"otp": "000000"}, headers=_auth(BUYER))
    assert res.status_code == 400


@patch("routes.call_service")
def test_buyer_verify_wrong_status(mock_svc, client):
    transfer = {**MOCK_TRANSFER, "status": "pending_seller_acceptance"}
    mock_svc.return_value = (transfer, None)
    res = client.post("/transfer/txr_001/buyer-verify",
                      json={"otp": "123456"}, headers=_auth(BUYER))
    assert res.status_code == 400


@patch("routes.call_service")
def test_buyer_verify_wrong_user(mock_svc, client):
    mock_svc.return_value = (MOCK_TRANSFER, None)
    res = client.post("/transfer/txr_001/buyer-verify",
                      json={"otp": "123456"}, headers=_auth(SELLER))
    assert res.status_code == 403


# ── POST /transfer/<id>/seller-accept ────────────────────────────────────────

@patch("routes.call_service")
def test_seller_accept_success(mock_svc, client):
    transfer = {**MOCK_TRANSFER, "status": "pending_seller_acceptance", "buyerOtpVerified": True}
    mock_svc.side_effect = [
        (transfer, None),
        (MOCK_BUYER_USER, None),
        ({"sid": "VE_buyer"}, None),
        (None, None),
    ]
    res = client.post("/transfer/txr_001/seller-accept", headers=_auth(SELLER))
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "pending_buyer_otp"


@patch("routes.call_service")
def test_seller_accept_not_seller(mock_svc, client):
    transfer = {**MOCK_TRANSFER, "status": "pending_seller_acceptance"}
    mock_svc.return_value = (transfer, None)
    res = client.post("/transfer/txr_001/seller-accept", headers=_auth(BUYER))
    assert res.status_code == 403


@patch("routes.call_service")
def test_seller_accept_wrong_status(mock_svc, client):
    mock_svc.return_value = (MOCK_TRANSFER, None)   # still pending_buyer_otp
    res = client.post("/transfer/txr_001/seller-accept", headers=_auth(SELLER))
    assert res.status_code == 400


# ── POST /transfer/<id>/seller-verify — happy path ───────────────────────────

@patch("routes.call_credit_service")
@patch("routes.call_service")
def test_seller_verify_full_saga_success(mock_svc, mock_credit, client):
    transfer = {
        **MOCK_TRANSFER,
        "status": "pending_seller_otp",
        "sellerOtpVerified": False,
        "sellerVerificationSid": "VE_seller",
        "buyerOtpVerified": True,
    }
    mock_svc.side_effect = [
        (transfer, None),                   # GET transfer
        ({"verified": True}, None),         # POST otp/verify
        (None, None),                       # PATCH sellerOtpVerified
        (MOCK_LISTING, None),               # GET listing
        (None, None),                       # PATCH ticket
        (None, None),                       # PATCH listing
        (None, None),                       # PATCH transfer completed
        (None, None),                       # POST buyer txn
        (None, None),                       # POST seller txn
    ]
    mock_credit.side_effect = [
        ({"creditBalance": 200.0}, None),   # GET buyer balance
        ({"creditBalance": 50.0}, None),    # GET seller balance
        ({}, None),                         # PATCH buyer deduct
        ({}, None),                         # PATCH seller credit
    ]
    res = client.post("/transfer/txr_001/seller-verify",
                      json={"otp": "654321"}, headers=_auth(SELLER))
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "completed"
    assert res.get_json()["data"]["ticket"]["newOwnerId"] == BUYER


# ── POST /transfer/<id>/seller-verify — failure scenarios ────────────────────

@patch("routes.call_service")
def test_seller_verify_wrong_otp(mock_svc, client):
    transfer = {**MOCK_TRANSFER, "status": "pending_seller_otp",
                "sellerOtpVerified": False, "sellerVerificationSid": "VE_seller"}
    mock_svc.side_effect = [
        (transfer, None),
        ({"verified": False}, None),
    ]
    res = client.post("/transfer/txr_001/seller-verify",
                      json={"otp": "000000"}, headers=_auth(SELLER))
    assert res.status_code == 400


@patch("routes.call_credit_service")
@patch("routes.call_service")
def test_seller_verify_insufficient_credits_at_execution(mock_svc, mock_credit, client):
    """Buyer drained credits between initiation and execution."""
    transfer = {**MOCK_TRANSFER, "status": "pending_seller_otp",
                "sellerOtpVerified": False, "sellerVerificationSid": "VE_seller"}
    mock_svc.side_effect = [
        (transfer, None),           # GET transfer
        ({"verified": True}, None), # POST otp/verify
        (None, None),               # PATCH sellerOtpVerified
        (MOCK_LISTING, None),       # GET listing
        (None, None),               # PATCH transfer → failed  ← this was missing
    ]
    mock_credit.return_value = ({"creditBalance": 5.0}, None)   # insufficient now
    res = client.post("/transfer/txr_001/seller-verify",
                      json={"otp": "654321"}, headers=_auth(SELLER))
    assert res.status_code == 402
    assert res.get_json()["error"]["code"] == "INSUFFICIENT_CREDITS"


@patch("routes.call_credit_service")
@patch("routes.call_service")
def test_seller_verify_saga_compensation_on_failure(mock_svc, mock_credit, client):
    """If saga fails after credits deducted, OutSystems balances must be restored."""
    transfer = {**MOCK_TRANSFER, "status": "pending_seller_otp",
                "sellerOtpVerified": False, "sellerVerificationSid": "VE_seller"}
    mock_svc.side_effect = [
        (transfer, None),
        ({"verified": True}, None),
        (None, None),           # PATCH sellerOtpVerified
        (MOCK_LISTING, None),   # GET listing
        Exception("ticket service down"),   # step 5 fails
    ]
    mock_credit.side_effect = [
        ({"creditBalance": 200.0}, None),   # GET buyer
        ({"creditBalance": 50.0}, None),    # GET seller
        ({}, None),                         # PATCH buyer deduct   (step 1)
        ({}, None),                         # PATCH seller credit  (step 2)
        ({}, None),                         # COMP: restore seller
        ({}, None),                         # COMP: restore buyer
    ]
    res = client.post("/transfer/txr_001/seller-verify",
                      json={"otp": "654321"}, headers=_auth(SELLER))
    assert res.status_code == 500
    assert res.get_json()["error"]["code"] == "INTERNAL_ERROR"
    # 4 credit calls: 2 deduct/credit + 2 compensations
    assert mock_credit.call_count == 6


# ── GET /transfer/<id> ────────────────────────────────────────────────────────

@patch("routes.call_service")
def test_get_transfer_buyer(mock_svc, client):
    mock_svc.return_value = (MOCK_TRANSFER, None)
    res = client.get("/transfer/txr_001", headers=_auth(BUYER))
    assert res.status_code == 200


@patch("routes.call_service")
def test_get_transfer_seller(mock_svc, client):
    mock_svc.return_value = (MOCK_TRANSFER, None)
    assert client.get("/transfer/txr_001", headers=_auth(SELLER)).status_code == 200


@patch("routes.call_service")
def test_get_transfer_third_party_denied(mock_svc, client):
    mock_svc.return_value = (MOCK_TRANSFER, None)
    res = client.get("/transfer/txr_001", headers=_auth("usr_stranger"))
    assert res.status_code == 403


# ── POST /transfer/<id>/cancel ────────────────────────────────────────────────

@patch("routes.call_service")
def test_cancel_success(mock_svc, client):
    mock_svc.side_effect = [
        (MOCK_TRANSFER, None),
        (None, None),
        (MOCK_LISTING, None),
        (None, None),
        (None, None),
    ]
    res = client.post("/transfer/txr_001/cancel", headers=_auth(BUYER))
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "cancelled"


@patch("routes.call_service")
def test_cancel_completed_transfer(mock_svc, client):
    transfer = {**MOCK_TRANSFER, "status": "completed"}
    mock_svc.return_value = (transfer, None)
    assert client.post("/transfer/txr_001/cancel", headers=_auth(BUYER)).status_code == 400
