import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import bcrypt
import jwt


def make_token(user_id="usr_001", role="user", venue_id=None):
    payload = {
        "userId": user_id, "email": "t@t.com", "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    if venue_id:
        payload["venueId"] = venue_id
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


def auth(user_id="usr_001", role="user"):
    return {"Authorization": f"Bearer {make_token(user_id, role)}"}


# ── /health ──────────────────────────────────────────────────────────────────

def test_health(client):
    assert client.get("/health").status_code == 200


# ── POST /auth/register ───────────────────────────────────────────────────────

@patch("routes.call_credit_service")
@patch("routes.call_service")
def test_register_success(mock_svc, mock_credit, client):
    mock_svc.return_value = (
        {"userId": "u1", "email": "a@b.com", "role": "user", "createdAt": "2025-01-01T00:00:00"},
        None,
    )
    mock_credit.return_value = ({}, None)

    res = client.post("/auth/register", json={
        "email": "a@b.com", "password": "Pass1!", "phoneNumber": "+6591234567",
    })
    assert res.status_code == 201
    assert res.get_json()["data"]["email"] == "a@b.com"
    assert mock_credit.call_args.kwargs["json"] == {"userId": "u1", "creditBalance": 0}


@patch("routes.call_credit_service")
@patch("routes.call_service")
def test_register_missing_fields(mock_svc, mock_credit, client):
    res = client.post("/auth/register", json={"email": "x@y.com"})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"


@patch("routes.call_credit_service")
@patch("routes.call_service")
def test_register_email_exists(mock_svc, mock_credit, client):
    mock_svc.return_value = (None, "EMAIL_ALREADY_EXISTS")
    res = client.post("/auth/register", json={
        "email": "dup@b.com", "password": "Pass1!", "phoneNumber": "+6591234567",
    })
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


@patch("routes.call_service")
@patch("routes.call_credit_service")
def test_register_credit_failure_deletes_user(mock_credit, mock_svc, client):
    """Credit init failure must trigger a compensating DELETE on the user."""
    mock_svc.side_effect = [
        ({"userId": "u1", "email": "a@b.com", "role": "user", "createdAt": "2025-01-01"}, None),
        (None, None),  # compensating DELETE
    ]
    mock_credit.return_value = (None, "SERVICE_UNAVAILABLE")

    res = client.post("/auth/register", json={
        "email": "a@b.com", "password": "Pass1!", "phoneNumber": "+6591234567",
    })
    assert res.status_code == 500
    # Verify DELETE was called as compensation
    delete_call = mock_svc.call_args_list[1]
    assert delete_call[0][0] == "DELETE"


# ── POST /auth/login ──────────────────────────────────────────────────────────

@patch("routes.call_service")
def test_login_success(mock_svc, client):
    pw = bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode()
    mock_svc.return_value = ({
        "userId": "u1", "email": "a@b.com", "password": pw,
        "role": "user", "isFlagged": False,
    }, None)

    res = client.post("/auth/login", json={"email": "a@b.com", "password": "Pass1!"})
    assert res.status_code == 200
    assert "token" in res.get_json()["data"]


@patch("routes.call_service")
def test_login_wrong_password(mock_svc, client):
    pw = bcrypt.hashpw(b"CorrectPass!", bcrypt.gensalt()).decode()
    mock_svc.return_value = ({
        "userId": "u1", "email": "a@b.com", "password": pw,
        "role": "user", "isFlagged": False,
    }, None)

    res = client.post("/auth/login", json={"email": "a@b.com", "password": "WrongPass!"})
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


@patch("routes.call_service")
def test_login_user_not_found(mock_svc, client):
    mock_svc.return_value = (None, "USER_NOT_FOUND")
    res = client.post("/auth/login", json={"email": "ghost@b.com", "password": "x"})
    assert res.status_code == 401


@patch("routes.call_service")
def test_login_flagged_account(mock_svc, client):
    pw = bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode()
    mock_svc.return_value = ({
        "userId": "u1", "email": "a@b.com", "password": pw,
        "role": "user", "isFlagged": True,
    }, None)

    res = client.post("/auth/login", json={"email": "a@b.com", "password": "Pass1!"})
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "AUTH_FORBIDDEN"


def test_login_missing_fields(client):
    res = client.post("/auth/login", json={"email": "a@b.com"})
    assert res.status_code == 400


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@patch("routes.call_service")
def test_me_success(mock_svc, client):
    mock_svc.return_value = ({
        "userId": "u1", "email": "a@b.com", "phoneNumber": "+65",
        "role": "user", "isFlagged": False, "createdAt": "2025-01-01",
    }, None)

    res = client.get("/auth/me", headers=auth())
    assert res.status_code == 200
    assert res.get_json()["data"]["email"] == "a@b.com"


def test_me_no_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_invalid_token(client):
    res = client.get("/auth/me", headers={"Authorization": "Bearer bad.token"})
    assert res.status_code == 401


# ── Staff login includes venueId in token ─────────────────────────────────────

@patch("routes.call_service")
def test_staff_login_embeds_venue_id(mock_svc, client):
    pw = bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode()
    mock_svc.return_value = ({
        "userId": "staff1", "email": "staff@b.com", "password": pw,
        "role": "staff", "isFlagged": False, "venueId": "ven_001",
    }, None)

    res = client.post("/auth/login", json={"email": "staff@b.com", "password": "Pass1!"})
    assert res.status_code == 200
    token = res.get_json()["data"]["token"]
    decoded = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    assert decoded["venueId"] == "ven_001"
