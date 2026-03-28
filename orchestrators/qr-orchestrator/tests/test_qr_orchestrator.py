"""Tests for qr-orchestrator."""
import os
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt


def _token(user_id="usr_001"):
    return jwt.encode(
        {"userId": user_id, "email": "t@t.com", "role": "user",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        os.environ["JWT_SECRET"], algorithm="HS256",
    )


def _auth(user_id="usr_001"):
    return {"Authorization": f"Bearer {_token(user_id)}"}


MOCK_TICKET = {
    "ticketId":    "tkt_001",
    "ownerId":     "usr_001",
    "eventId":     "evt_001",
    "venueId":     "ven_001",
    "inventoryId": "inv_001",
    "status":      "active",
    "price":       80.0,
    "createdAt":   "2025-01-01T00:00:00",
}
MOCK_EVENT = {"eventId": "evt_001", "name": "Symphony Night", "date": "2025-03-20T19:30:00"}
MOCK_VENUE = {"venueId": "ven_001", "name": "Esplanade", "address": "1 Esplanade Dr"}


def test_health(client):
    assert client.get("/health").status_code == 200


# ── GET /tickets ──────────────────────────────────────────────────────────────

@patch("routes.call_service")
def test_list_tickets_success(mock_svc, client):
    mock_svc.side_effect = [
        ({"tickets": [MOCK_TICKET]}, None),
        (MOCK_EVENT, None),
        (MOCK_VENUE, None),
    ]
    res = client.get("/tickets", headers=_auth())
    assert res.status_code == 200
    tickets = res.get_json()["data"]["tickets"]
    assert len(tickets) == 1
    assert tickets[0]["event"]["name"] == "Symphony Night"


def test_list_tickets_no_auth(client):
    assert client.get("/tickets").status_code == 401


# ── GET /tickets/<id>/qr ──────────────────────────────────────────────────────

@patch("routes.call_service")
def test_get_qr_success(mock_svc, client):
    mock_svc.side_effect = [
        (MOCK_TICKET, None),    # GET ticket
        (None, None),           # PATCH qrHash
        (MOCK_EVENT, None),
        (MOCK_VENUE, None),
    ]
    res = client.get("/tickets/tkt_001/qr", headers=_auth())
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data["qrHash"]) == 64   # SHA-256 hex
    assert "expiresAt" in data


@patch("routes.call_service")
def test_get_qr_not_found(mock_svc, client):
    mock_svc.return_value = (None, "TICKET_NOT_FOUND")
    assert client.get("/tickets/tkt_bad/qr", headers=_auth()).status_code == 404


@patch("routes.call_service")
def test_get_qr_not_owner(mock_svc, client):
    ticket = {**MOCK_TICKET, "ownerId": "usr_other"}
    mock_svc.return_value = (ticket, None)
    res = client.get("/tickets/tkt_001/qr", headers=_auth("usr_001"))
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "AUTH_FORBIDDEN"


@patch("routes.call_service")
def test_get_qr_listed_ticket_rejected(mock_svc, client):
    ticket = {**MOCK_TICKET, "status": "listed"}
    mock_svc.return_value = (ticket, None)
    res = client.get("/tickets/tkt_001/qr", headers=_auth())
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "QR_INVALID"


@patch("routes.call_service")
def test_get_qr_used_ticket_rejected(mock_svc, client):
    ticket = {**MOCK_TICKET, "status": "used"}
    mock_svc.return_value = (ticket, None)
    res = client.get("/tickets/tkt_001/qr", headers=_auth())
    assert res.status_code == 400


@patch("routes.call_service")
def test_get_qr_pending_transfer_rejected(mock_svc, client):
    ticket = {**MOCK_TICKET, "status": "pending_transfer"}
    mock_svc.return_value = (ticket, None)
    res = client.get("/tickets/tkt_001/qr", headers=_auth())
    assert res.status_code == 400


@patch("routes.call_service")
def test_qr_hashes_are_unique_per_call(mock_svc, client):
    """Each call must return a different qrHash (different timestamp)."""
    mock_svc.side_effect = [
        (MOCK_TICKET, None), (None, None), (MOCK_EVENT, None), (MOCK_VENUE, None),
        (MOCK_TICKET, None), (None, None), (MOCK_EVENT, None), (MOCK_VENUE, None),
    ]
    r1 = client.get("/tickets/tkt_001/qr", headers=_auth())
    time.sleep(0.01)
    r2 = client.get("/tickets/tkt_001/qr", headers=_auth())
    assert r1.get_json()["data"]["qrHash"] != r2.get_json()["data"]["qrHash"]


def test_get_qr_no_auth(client):
    assert client.get("/tickets/tkt_001/qr").status_code == 401
