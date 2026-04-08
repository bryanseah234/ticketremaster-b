"""Tests for ticket-purchase-orchestrator."""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt


def _token(user_id="usr_001"):
    return jwt.encode(
        {"userId": user_id, "email": "t@t.com", "role": "user",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        os.environ["JWT_SECRET"], algorithm="HS256",
    )


def _auth(user_id="usr_001"):
    return {"Authorization": f"Bearer {_token(user_id)}"}


def test_health(client):
    assert client.get("/health").status_code == 200


def test_hold_no_auth(client):
    assert client.post("/purchase/hold/inv_001").status_code == 401


@patch("routes._publish_hold_ttl")
@patch("routes._grpc_stub")
def test_hold_success(mock_stub, mock_publish, client):
    stub = MagicMock()
    stub.HoldSeat.return_value = MagicMock(
        success=True, status="held",
        held_until=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        hold_token="tok_abc",
        error_code="",
    )
    mock_stub.return_value = stub

    res = client.post("/purchase/hold/inv_001", headers=_auth())
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "held"
    mock_publish.assert_called_once()


@patch("routes._grpc_stub")
def test_hold_seat_unavailable(mock_stub, client):
    stub = MagicMock()
    stub.HoldSeat.return_value = MagicMock(success=False, error_code="SEAT_NOT_AVAILABLE")
    mock_stub.return_value = stub
    res = client.post("/purchase/hold/inv_001", headers=_auth())
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "SEAT_NOT_AVAILABLE"


@patch("routes.call_service")
@patch("routes.call_credit_service")
@patch("routes._get_cached_hold")
@patch("routes._grpc_stub")
def test_confirm_success(mock_stub, mock_cached_hold, mock_credit, mock_svc, client):
    stub = MagicMock()
    stub.GetSeatStatus.return_value = MagicMock(
        status="held",
        held_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        inventory_id="inv_001",
    )
    stub.SellSeat.return_value = MagicMock(success=True)
    mock_stub.return_value = stub
    mock_cached_hold.return_value = None

    mock_credit.side_effect = [
        ({"creditBalance": 200.0}, None),
        ({}, None),
    ]
    mock_svc.side_effect = [
        ({"eventId": "evt_001", "venueId": "ven_001", "price": 80.0}, None),
        ({"ticketId": "tkt_001", "createdAt": "2025-01-01"}, None),
        (None, None),
    ]

    res = client.post("/purchase/confirm/inv_001",
                      json={"eventId": "evt_001", "holdToken": "tok_abc"},
                      headers=_auth())
    assert res.status_code == 201
    assert res.get_json()["data"]["ticketId"] == "tkt_001"


@patch("routes.call_service")
@patch("routes.call_credit_service")
@patch("routes._get_cached_hold")
@patch("routes._grpc_stub")
def test_confirm_success_uses_cached_hold(mock_stub, mock_cached_hold, mock_credit, mock_svc, client):
    stub = MagicMock()
    stub.SellSeat.return_value = MagicMock(success=True)
    mock_stub.return_value = stub
    mock_cached_hold.return_value = {
        "status": "held",
        "heldByUserId": "usr_001",
        "holdToken": "tok_abc",
        "heldUntil": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    }

    mock_credit.side_effect = [
        ({"creditBalance": 200.0}, None),
        ({}, None),
    ]
    mock_svc.side_effect = [
        ({"eventId": "evt_001", "venueId": "ven_001", "price": 80.0}, None),
        ({"ticketId": "tkt_001", "createdAt": "2025-01-01"}, None),
        (None, None),
    ]

    res = client.post(
        "/purchase/confirm/inv_001",
        json={"eventId": "evt_001", "holdToken": "tok_abc"},
        headers=_auth(),
    )

    assert res.status_code == 201
    stub.GetSeatStatus.assert_not_called()


@patch("routes.call_service")
@patch("routes.call_credit_service")
@patch("routes._grpc_stub")
def test_confirm_requires_event_id(mock_stub, mock_credit, mock_svc, client):
    stub = MagicMock()
    stub.GetSeatStatus.return_value = MagicMock(
        status="held",
        held_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    )
    mock_stub.return_value = stub

    res = client.post(
        "/purchase/confirm/inv_001",
        json={"holdToken": "tok_abc"},
        headers=_auth(),
    )

    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"
    mock_credit.assert_not_called()
    mock_svc.assert_not_called()


@patch("routes._grpc_stub")
def test_confirm_hold_expired(mock_stub, client):
    stub = MagicMock()
    stub.GetSeatStatus.return_value = MagicMock(
        status="held",
        held_until=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
    )
    mock_stub.return_value = stub
    res = client.post("/purchase/confirm/inv_001", json={"eventId": "evt_001"}, headers=_auth())
    assert res.status_code == 410
    assert res.get_json()["error"]["code"] == "PAYMENT_HOLD_EXPIRED"


@patch("routes._get_cached_hold")
@patch("routes._grpc_stub")
def test_confirm_cached_hold_token_mismatch(mock_stub, mock_cached_hold, client):
    mock_stub.return_value = MagicMock()
    mock_cached_hold.return_value = {
        "status": "held",
        "heldByUserId": "usr_001",
        "holdToken": "tok_other",
        "heldUntil": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    }

    res = client.post(
        "/purchase/confirm/inv_001",
        json={"eventId": "evt_001", "holdToken": "tok_abc"},
        headers=_auth(),
    )

    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "SEAT_UNAVAILABLE"


@patch("routes.call_service")
@patch("routes.call_credit_service")
@patch("routes._get_cached_hold")
@patch("routes._grpc_stub")
def test_confirm_insufficient_credits(mock_stub, mock_cached_hold, mock_credit, mock_svc, client):
    stub = MagicMock()
    stub.GetSeatStatus.return_value = MagicMock(
        status="held",
        held_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    )
    mock_stub.return_value = stub
    mock_cached_hold.return_value = None
    mock_credit.return_value = ({"creditBalance": 5.0}, None)
    mock_svc.side_effect = [
        ({"eventId": "evt_001", "venueId": "ven_001", "price": 80.0}, None),
    ]
    res = client.post("/purchase/confirm/inv_001", json={"eventId": "evt_001"}, headers=_auth())
    assert res.status_code == 402
    assert res.get_json()["error"]["code"] == "INSUFFICIENT_CREDITS"


@patch("routes.call_service")
@patch("routes.call_credit_service")
@patch("routes._get_cached_hold")
@patch("routes._grpc_stub")
def test_confirm_ticket_failure_releases_seat(mock_stub, mock_cached_hold, mock_credit, mock_svc, client):
    stub = MagicMock()
    stub.GetSeatStatus.return_value = MagicMock(
        status="held",
        held_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    )
    stub.SellSeat.return_value = MagicMock(success=True)
    stub.ReleaseSeat.return_value = MagicMock(success=True)
    mock_stub.return_value = stub
    mock_cached_hold.return_value = None
    mock_credit.return_value = ({"creditBalance": 200.0}, None)
    mock_svc.side_effect = [
        ({"eventId": "evt_001", "venueId": "ven_001", "price": 80.0}, None),
        (None, "INTERNAL_ERROR"),  # ticket creation fails
    ]
    res = client.post("/purchase/confirm/inv_001", json={"eventId": "evt_001"}, headers=_auth())
    assert res.status_code == 500
    stub.ReleaseSeat.assert_called_once()


@patch("routes.call_service")
def test_resume_hold_unwraps_enriched_event_and_seat_payloads(mock_svc, client):
    mock_svc.side_effect = [
        ({
            "data": {
                "inventoryId": "inv_001",
                "holdToken": "tok_abc",
                "heldUntil": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                "seatId": "seat_001",
            }
        }, None),
        ({
            "data": {
                "seatId": "seat_001",
                "rowNumber": "A",
                "seatNumber": "12",
                "section": "VIP",
            }
        }, None),
        ({
            "data": {
                "eventId": "evt_001",
                "name": "Taylor Swift | The Eras Tour",
                "date": "2026-06-15T19:30:00",
                "price": 248.0,
                "image": "https://cdn.example.test/eras.jpg",
                "venue": {"name": "National Stadium"},
            }
        }, None),
    ]

    res = client.get("/purchase/hold/resume/evt_001", headers=_auth())
    assert res.status_code == 200
    payload = res.get_json()["data"]
    assert payload["seat"]["rowNumber"] == "A"
    assert payload["seat"]["seatNumber"] == "12"
    assert payload["seat"]["section"] == "VIP"
    assert payload["seat"]["price"] == 248.0
    assert payload["event"]["name"] == "Taylor Swift | The Eras Tour"
    assert payload["event"]["venueName"] == "National Stadium"
