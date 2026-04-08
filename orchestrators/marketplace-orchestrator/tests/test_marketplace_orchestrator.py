"""Tests for marketplace-orchestrator."""
import os
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
}
MOCK_LISTING = {
    "listingId": "lst_001",
    "ticketId":  "tkt_001",
    "sellerId":  "usr_001",
    "price":     80.0,
    "status":    "active",
    "createdAt": "2025-01-15T11:00:00",
}
MOCK_EVENT = {"eventId": "evt_001", "name": "Symphony Night", "date": "2025-03-20T19:30:00"}
MOCK_SELLER = {"userId": "usr_001", "email": "usr_001@ticketremaster.local"}


def test_health(client):
    assert client.get("/health").status_code == 200


# ── GET /marketplace ──────────────────────────────────────────────────────────

@patch("routes.call_service")
def test_browse_success(mock_svc, client):
    mock_svc.side_effect = [
        ({"listings": [MOCK_LISTING], "pagination": {}}, None),
        (MOCK_TICKET, None),
        (MOCK_EVENT, None),
        (MOCK_SELLER, None),
    ]
    res = client.get("/marketplace")
    assert res.status_code == 200
    assert len(res.get_json()["data"]["listings"]) == 1
    assert res.get_json()["data"]["listings"][0]["event"]["name"] == "Symphony Night"
    assert res.get_json()["data"]["listings"][0]["sellerName"] == "usr_001"


@patch("routes.call_service")
def test_browse_filters_by_event_id(mock_svc, client):
    other_ticket = {**MOCK_TICKET, "ticketId": "tkt_002", "eventId": "evt_999"}
    other_listing = {**MOCK_LISTING, "listingId": "lst_002", "ticketId": "tkt_002"}
    other_event = {"eventId": "evt_999", "name": "Other Event", "date": "2025-04-01T20:00:00"}

    mock_svc.side_effect = [
        ({"listings": [MOCK_LISTING, other_listing], "pagination": {"page": 1, "limit": 20, "total": 2}}, None),
        (MOCK_TICKET, None),
        (MOCK_EVENT, None),
        (MOCK_SELLER, None),
        (other_ticket, None),
        (other_event, None),
        (MOCK_SELLER, None),
    ]

    res = client.get("/marketplace?eventId=evt_001")

    assert res.status_code == 200
    payload = res.get_json()["data"]
    assert payload["pagination"] == {"page": 1, "limit": 20, "total": 1}
    assert [listing["listingId"] for listing in payload["listings"]] == ["lst_001"]


@patch("routes.call_service")
def test_browse_no_auth_required(mock_svc, client):
    """GET /marketplace must be accessible without a JWT."""
    mock_svc.return_value = ({"listings": [], "pagination": {}}, None)
    assert client.get("/marketplace").status_code == 200


@patch("routes.call_service")
def test_browse_rejects_invalid_limit(mock_svc, client):
    res = client.get("/marketplace?limit=0")

    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"


@patch("routes.call_service")
def test_get_listing_success(mock_svc, client):
    mock_svc.side_effect = [
        (MOCK_LISTING, None),
        (MOCK_TICKET, None),
        (MOCK_EVENT, None),
        (MOCK_SELLER, None),
    ]

    res = client.get("/marketplace/lst_001")

    assert res.status_code == 200
    payload = res.get_json()["data"]
    assert payload["listingId"] == "lst_001"
    assert payload["event"]["name"] == "Symphony Night"
    assert payload["sellerName"] == "usr_001"


@patch("routes.call_service")
def test_get_listing_not_found(mock_svc, client):
    mock_svc.return_value = (None, "LISTING_NOT_FOUND")

    res = client.get("/marketplace/lst_missing")

    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "LISTING_NOT_FOUND"


# ── POST /marketplace/list ────────────────────────────────────────────────────

@patch("routes.call_service")
def test_list_ticket_success(mock_svc, client):
    mock_svc.side_effect = [
        (MOCK_TICKET, None),    # GET ticket
        (None, None),           # PATCH ticket → listed
        (MOCK_LISTING, None),   # POST listing
    ]
    res = client.post("/marketplace/list", json={"ticketId": "tkt_001"}, headers=_auth())
    assert res.status_code == 201
    assert res.get_json()["data"]["listingId"] == "lst_001"


@patch("routes.call_service")
def test_list_ticket_missing_ticket_id(mock_svc, client):
    res = client.post("/marketplace/list", json={}, headers=_auth())
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"


@patch("routes.call_service")
def test_list_ticket_not_owner(mock_svc, client):
    ticket = {**MOCK_TICKET, "ownerId": "usr_other"}
    mock_svc.return_value = (ticket, None)
    res = client.post("/marketplace/list", json={"ticketId": "tkt_001"}, headers=_auth("usr_001"))
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "AUTH_FORBIDDEN"


@patch("routes.call_service")
def test_list_ticket_already_listed(mock_svc, client):
    ticket = {**MOCK_TICKET, "status": "listed"}
    mock_svc.return_value = (ticket, None)
    res = client.post("/marketplace/list", json={"ticketId": "tkt_001"}, headers=_auth())
    assert res.status_code == 400


@patch("routes.call_service")
def test_list_ticket_used(mock_svc, client):
    ticket = {**MOCK_TICKET, "status": "used"}
    mock_svc.return_value = (ticket, None)
    assert client.post("/marketplace/list", json={"ticketId": "tkt_001"}, headers=_auth()).status_code == 400


@patch("routes.call_service")
def test_list_ticket_compensates_on_listing_failure(mock_svc, client):
    """If listing creation fails, ticket must be reverted to active."""
    mock_svc.side_effect = [
        (MOCK_TICKET, None),        # GET ticket
        (None, None),               # PATCH → listed
        (None, "INTERNAL_ERROR"),   # POST listing fails
        (None, None),               # PATCH → active (compensation)
    ]
    res = client.post("/marketplace/list", json={"ticketId": "tkt_001"}, headers=_auth())
    assert res.status_code == 500
    patch_calls = [c for c in mock_svc.call_args_list if c[0][0] == "PATCH"]
    assert len(patch_calls) == 2
    assert patch_calls[1][1]["json"]["status"] == "active"


def test_list_ticket_no_auth(client):
    assert client.post("/marketplace/list", json={"ticketId": "tkt_001"}).status_code == 401


# ── DELETE /marketplace/<listing_id> ─────────────────────────────────────────

@patch("routes.call_service")
def test_delist_success(mock_svc, client):
    mock_svc.side_effect = [
        (MOCK_LISTING, None),   # GET listing
        (None, None),           # PATCH → cancelled
        (None, None),           # PATCH ticket → active
    ]
    res = client.delete("/marketplace/lst_001", headers=_auth())
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "cancelled"


@patch("routes.call_service")
def test_delist_not_owner(mock_svc, client):
    listing = {**MOCK_LISTING, "sellerId": "usr_other"}
    mock_svc.return_value = (listing, None)
    res = client.delete("/marketplace/lst_001", headers=_auth("usr_001"))
    assert res.status_code == 403


@patch("routes.call_service")
def test_delist_completed_listing(mock_svc, client):
    listing = {**MOCK_LISTING, "status": "completed"}
    mock_svc.return_value = (listing, None)
    assert client.delete("/marketplace/lst_001", headers=_auth()).status_code == 400


@patch("routes.call_service")
def test_delist_not_found(mock_svc, client):
    mock_svc.return_value = (None, "LISTING_NOT_FOUND")
    assert client.delete("/marketplace/lst_bad", headers=_auth()).status_code == 404


def test_delist_no_auth(client):
    assert client.delete("/marketplace/lst_001").status_code == 401
