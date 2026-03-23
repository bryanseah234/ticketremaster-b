"""Tests for ticket-verification-orchestrator.

Covers all 8 checks in strict order:
  1. QR not found
  2. QR TTL expired
  3. Event not found
  4. Seat not sold
  5. Ticket not active
  6. Duplicate scan
  7. Wrong venue
  8. All pass → checked_in

Also verifies venueId always comes from JWT, never from request body.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest


def _staff_token(user_id="staff_001", venue_id="ven_001"):
    payload = {
        "userId": user_id, "email": "staff@t.com", "role": "staff",
        "venueId": venue_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


def _user_token(user_id="usr_001"):
    return jwt.encode(
        {"userId": user_id, "email": "u@t.com", "role": "user",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        os.environ["JWT_SECRET"], algorithm="HS256",
    )


def _staff_headers(venue_id="ven_001"):
    return {"Authorization": f"Bearer {_staff_token(venue_id=venue_id)}"}


def _user_headers():
    return {"Authorization": f"Bearer {_user_token()}"}


FRESH_TS   = datetime.now(timezone.utc).isoformat()
EXPIRED_TS = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()

MOCK_TICKET = {
    "ticketId":    "tkt_001",
    "ownerId":     "usr_001",
    "eventId":     "evt_001",
    "venueId":     "ven_001",
    "inventoryId": "inv_001",
    "status":      "active",
    "qrTimestamp": FRESH_TS,
}
MOCK_EVENT = {
    "eventId": "evt_001", "name": "Symphony Night",
    "date": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
}
MOCK_INV_LIST = {"eventId": "evt_001", "inventory": [
    {"inventoryId": "inv_001", "seatId": "seat_001", "status": "sold", "heldUntil": None},
]}
MOCK_VENUE       = {"venueId": "ven_001", "name": "Esplanade", "address": "1 Esplanade Dr"}
MOCK_WRONG_VENUE = {"venueId": "ven_002", "name": "Indoor Stadium", "address": "2 Stadium Walk"}


def test_health(client):
    assert client.get("/health").status_code == 200


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_scan_no_auth(client):
    assert client.post("/verify/scan", json={"qrHash": "abc"}).status_code == 401


def test_scan_user_role_rejected(client):
    res = client.post("/verify/scan", json={"qrHash": "abc"}, headers=_user_headers())
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "AUTH_FORBIDDEN"


def test_scan_missing_qr_hash(client):
    res = client.post("/verify/scan", json={}, headers=_staff_headers())
    assert res.status_code == 400


# ── Check 1: QR not found ─────────────────────────────────────────────────────

@patch("routes.call_service")
def test_qr_not_found(mock_svc, client):
    mock_svc.return_value = (None, "TICKET_NOT_FOUND")
    res = client.post("/verify/scan", json={"qrHash": "unknown"}, headers=_staff_headers())
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "TICKET_NOT_FOUND"


# ── Check 2: QR TTL expired ───────────────────────────────────────────────────

@patch("routes.call_service")
def test_qr_expired(mock_svc, client):
    ticket = {**MOCK_TICKET, "qrTimestamp": EXPIRED_TS}
    mock_svc.side_effect = [
        (ticket, None),   # GET ticket
        (None, None),     # POST log expired
    ]
    res = client.post("/verify/scan", json={"qrHash": "old"}, headers=_staff_headers())
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "QR_EXPIRED"
    # Verify expired was logged
    log_call = mock_svc.call_args_list[1]
    assert log_call[1]["json"]["status"] == "expired"


# ── Check 3: Event not found ──────────────────────────────────────────────────

@patch("routes.call_service")
def test_event_not_found(mock_svc, client):
    mock_svc.side_effect = [
        (MOCK_TICKET, None),
        (None, "EVENT_NOT_FOUND"),
        (None, None),   # log invalid
    ]
    res = client.post("/verify/scan", json={"qrHash": "h"}, headers=_staff_headers())
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "TICKET_NOT_FOUND"


# ── Check 4: Seat not sold ────────────────────────────────────────────────────

@patch("routes.call_service")
def test_seat_not_sold(mock_svc, client):
    inv = {"inventory": [{"inventoryId": "inv_001", "seatId": "s1", "status": "available"}]}
    mock_svc.side_effect = [
        (MOCK_TICKET, None),
        (MOCK_EVENT, None),
        (inv, None),
        (None, None),   # log invalid
    ]
    res = client.post("/verify/scan", json={"qrHash": "h"}, headers=_staff_headers())
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "TICKET_NOT_FOUND"


# ── Check 5: Ticket not active ────────────────────────────────────────────────

@patch("routes.call_service")
def test_ticket_not_active_listed(mock_svc, client):
    ticket = {**MOCK_TICKET, "status": "listed"}
    mock_svc.side_effect = [
        (ticket, None),
        (MOCK_EVENT, None),
        (MOCK_INV_LIST, None),
        (None, None),   # log invalid
    ]
    res = client.post("/verify/scan", json={"qrHash": "h"}, headers=_staff_headers())
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "QR_INVALID"


@patch("routes.call_service")
def test_ticket_not_active_used(mock_svc, client):
    ticket = {**MOCK_TICKET, "status": "used"}
    mock_svc.side_effect = [
        (ticket, None), (MOCK_EVENT, None), (MOCK_INV_LIST, None), (None, None)
    ]
    res = client.post("/verify/scan", json={"qrHash": "h"}, headers=_staff_headers())
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "QR_INVALID"


# ── Check 6: Duplicate scan ───────────────────────────────────────────────────

@patch("routes.call_service")
def test_duplicate_scan(mock_svc, client):
    existing_log = {"logs": [{"logId": "l1", "ticketId": "tkt_001", "status": "checked_in"}]}
    mock_svc.side_effect = [
        (MOCK_TICKET, None),
        (MOCK_EVENT, None),
        (MOCK_INV_LIST, None),
        (existing_log, None),
        (None, None),   # log duplicate
    ]
    res = client.post("/verify/scan", json={"qrHash": "h"}, headers=_staff_headers())
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "ALREADY_CHECKED_IN"
    # Verify duplicate was logged
    log_call = mock_svc.call_args_list[4]
    assert log_call[1]["json"]["status"] == "duplicate"


# ── Check 7: Wrong venue ──────────────────────────────────────────────────────

@patch("routes.call_service")
def test_wrong_venue(mock_svc, client):
    """Ticket is for ven_001 but staff JWT says ven_002."""
    mock_svc.side_effect = [
        (MOCK_TICKET, None),        # ticket venueId = ven_001
        (MOCK_EVENT, None),
        (MOCK_INV_LIST, None),
        ({"logs": []}, None),
        (MOCK_VENUE, None),         # GET correct venue
        (None, None),               # log wrong_venue
    ]
    res = client.post("/verify/scan", json={"qrHash": "h"},
                      headers={"Authorization": f"Bearer {_staff_token(venue_id='ven_002')}"})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "WRONG_HALL"
    assert res.get_json()["error"]["correctVenue"]["venueId"] == "ven_001"
    log_call = mock_svc.call_args_list[5]
    assert log_call[1]["json"]["status"] == "wrong_venue"


# ── Check 8: All pass ─────────────────────────────────────────────────────────

@patch("routes.call_service")
def test_scan_success(mock_svc, client):
    mock_svc.side_effect = [
        (MOCK_TICKET, None),
        (MOCK_EVENT, None),
        (MOCK_INV_LIST, None),
        ({"logs": []}, None),
        (None, None),   # PATCH ticket → used
        (None, None),   # POST log checked_in
    ]
    res = client.post("/verify/scan", json={"qrHash": "valid"}, headers=_staff_headers())
    assert res.status_code == 200
    assert res.get_json()["data"]["result"] == "SUCCESS"
    # Verify checked_in was logged
    log_call = mock_svc.call_args_list[5]
    assert log_call[1]["json"]["status"] == "checked_in"


# ── venueId security: must come from JWT only ─────────────────────────────────

@patch("routes.call_service")
def test_venue_id_from_jwt_not_body(mock_svc, client):
    """
    Staff is at ven_002 (in JWT).
    Ticket is for ven_001.
    Request body also contains venueId=ven_001 to try to spoof.
    Must still return WRONG_HALL because JWT says ven_002.
    """
    mock_svc.side_effect = [
        (MOCK_TICKET, None),
        (MOCK_EVENT, None),
        (MOCK_INV_LIST, None),
        ({"logs": []}, None),
        (MOCK_VENUE, None),
        (None, None),
    ]
    res = client.post(
        "/verify/scan",
        json={"qrHash": "h", "venueId": "ven_001"},  # attacker passes matching venueId
        headers={"Authorization": f"Bearer {_staff_token(venue_id='ven_002')}"},
    )
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "WRONG_HALL"


# ── Check order: expired QR must take precedence over duplicate ───────────────

@patch("routes.call_service")
def test_expired_checked_before_duplicate(mock_svc, client):
    """Even if ticket is already checked in, QR_EXPIRED must be returned first."""
    ticket = {**MOCK_TICKET, "qrTimestamp": EXPIRED_TS, "status": "used"}
    mock_svc.side_effect = [
        (ticket, None),
        (None, None),   # log expired
    ]
    res = client.post("/verify/scan", json={"qrHash": "old"}, headers=_staff_headers())
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "QR_EXPIRED"
