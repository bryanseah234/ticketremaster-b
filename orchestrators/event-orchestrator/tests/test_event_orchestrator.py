"""Tests for event-orchestrator."""
from unittest.mock import patch


MOCK_EVENT = {"eventId": "evt_001", "venueId": "ven_001", "name": "Symphony Night",
              "date": "2025-03-20T19:30:00", "type": "orchestra", "price": 80.0,
              "description": "Test", "createdAt": "2025-01-01T00:00:00"}
MOCK_VENUE = {"venueId": "ven_001", "name": "Esplanade", "address": "1 Esplanade Dr",
              "isActive": True}
MOCK_INV   = {"eventId": "evt_001", "inventory": [
    {"inventoryId": "inv_001", "seatId": "seat_001", "status": "available", "heldUntil": None},
    {"inventoryId": "inv_002", "seatId": "seat_002", "status": "held",      "heldUntil": None},
    {"inventoryId": "inv_003", "seatId": "seat_003", "status": "sold",      "heldUntil": None},
]}
MOCK_SEATS = {"seats": [
    {"seatId": "seat_001", "rowNumber": "A", "seatNumber": 1},
    {"seatId": "seat_002", "rowNumber": "A", "seatNumber": 2},
    {"seatId": "seat_003", "rowNumber": "A", "seatNumber": 3},
]}


def test_health(client):
    assert client.get("/health").status_code == 200


@patch("routes.call_service")
def test_list_events(mock_svc, client):
    mock_svc.side_effect = [
        ({"events": [MOCK_EVENT]}, None),
        (MOCK_VENUE, None),
        (MOCK_INV,   None),
    ]
    res = client.get("/events")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data["events"]) == 1
    assert data["events"][0]["seatsAvailable"] == 1
    assert data["events"][0]["venue"]["name"] == "Esplanade"


@patch("routes.call_service")
def test_list_events_service_down(mock_svc, client):
    mock_svc.return_value = (None, "SERVICE_UNAVAILABLE")
    assert client.get("/events").status_code == 503


@patch("routes.call_service")
def test_get_event_success(mock_svc, client):
    mock_svc.side_effect = [(MOCK_EVENT, None), (MOCK_VENUE, None)]
    res = client.get("/events/evt_001")
    assert res.status_code == 200
    assert res.get_json()["data"]["eventId"] == "evt_001"


@patch("routes.call_service")
def test_get_event_not_found(mock_svc, client):
    mock_svc.return_value = (None, "EVENT_NOT_FOUND")
    assert client.get("/events/bad").status_code == 404


@patch("routes.call_service")
def test_get_seat_map(mock_svc, client):
    mock_svc.side_effect = [(MOCK_EVENT, None), (MOCK_INV, None), (MOCK_SEATS, None)]
    res = client.get("/events/evt_001/seats")
    assert res.status_code == 200
    seats = res.get_json()["data"]["seats"]
    assert len(seats) == 3
    assert seats[0]["rowNumber"] == "A"
    assert seats[0]["seatNumber"] == 1
    assert seats[0]["price"] == 80.0


@patch("routes.call_service")
def test_get_seat_detail(mock_svc, client):
    mock_svc.side_effect = [(MOCK_EVENT, None), (MOCK_INV, None), (MOCK_VENUE, None)]
    res = client.get("/events/evt_001/seats/inv_001")
    assert res.status_code == 200
    assert res.get_json()["data"]["inventoryId"] == "inv_001"


@patch("routes.call_service")
def test_get_seat_detail_not_found(mock_svc, client):
    mock_svc.side_effect = [(MOCK_EVENT, None), (MOCK_INV, None), (MOCK_VENUE, None)]
    res = client.get("/events/evt_001/seats/inv_bad")
    assert res.status_code == 404


def test_events_no_auth_required(client):
    """All event endpoints are public."""
    # No Authorization header — should not 401
    with patch("routes.call_service") as mock_svc:
        mock_svc.return_value = ({"events": []}, None)
        assert client.get("/events").status_code == 200
