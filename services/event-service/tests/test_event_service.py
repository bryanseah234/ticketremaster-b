def event_data(name="Test Event", venueId="ven_001", **kwargs):
    data = {
        "venueId": venueId,
        "name": name,
        "date": "2025-06-15T19:30:00",
        "type": "concert",
        "price": 99.50,
    }
    data.update(kwargs)
    return data


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_list_events_empty(client):
    response = client.get("/events")
    assert response.status_code == 200
    assert response.get_json() == {"events": []}


def test_create_event(client):
    response = client.post("/events", json=event_data())
    assert response.status_code == 201
    payload = response.get_json()
    assert "eventId" in payload
    assert payload["venueId"] == "ven_001"
    assert payload["name"] == "Test Event"
    assert "createdAt" in payload


def test_create_event_missing_fields(client):
    response = client.post("/events", json={"name": "Incomplete"})
    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "VALIDATION_ERROR"


def test_get_event_by_id(client):
    created = client.post("/events", json=event_data()).get_json()
    event_id = created["eventId"]

    response = client.get(f"/events/{event_id}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["eventId"] == event_id
    assert payload["venueId"] == "ven_001"
    assert payload["name"] == "Test Event"
    assert payload["description"] is None
    assert payload["type"] == "concert"
    assert payload["price"] == 99.50
    assert "createdAt" in payload


def test_get_event_not_found(client):
    response = client.get("/events/nonexistent")
    assert response.status_code == 404
    error = response.get_json()["error"]
    assert error["code"] == "EVENT_NOT_FOUND"


def test_list_events_returns_created_events(client):
    data = event_data("Event One")
    client.post("/events", json=data)
    data = event_data("Event Two")
    client.post("/events", json=data)

    response = client.get("/events")
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["events"]) == 2
    assert payload["events"][0]["name"] == "Event One"
    assert payload["events"][1]["name"] == "Event Two"


def test_list_excludes_detail_fields(client):
    data = event_data(description="Detail", image="http://img.jpg")
    client.post("/events", json=data).get_json()

    response = client.get("/events")
    payload = response.get_json()
    event = payload["events"][0]

    assert "description" not in event
    assert "image" not in event
    assert "eventId" in event
    assert "name" in event
    assert "type" in event
    assert "price" in event

