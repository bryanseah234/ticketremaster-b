"""
Event Orchestrator — public read-only endpoints.
No JWT required. Aggregates event, venue, and seat-inventory data.
"""
import os

from flask import Blueprint, jsonify, request

from service_client import call_service

bp = Blueprint("events", __name__)

EVENT_SERVICE          = os.environ.get("EVENT_SERVICE_URL",           "http://event-service:5000")
VENUE_SERVICE          = os.environ.get("VENUE_SERVICE_URL",           "http://venue-service:5000")
SEAT_SERVICE           = os.environ.get("SEAT_SERVICE_URL",            "http://seat-service:5000")
SEAT_INVENTORY_SERVICE = os.environ.get("SEAT_INVENTORY_SERVICE_URL",  "http://seat-inventory-service:5000")


def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


# ── GET /events ───────────────────────────────────────────────────────────────

@bp.get("/events")
def list_events():
    params = {k: v for k, v in request.args.items() if k in ("type", "page", "limit")}
    events_data, err = call_service("GET", f"{EVENT_SERVICE}/events", params=params)
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not fetch events.", 503)

    enriched = []
    for event in events_data.get("events", []):
        venue, _      = call_service("GET", f"{VENUE_SERVICE}/venues/{event['venueId']}")
        inv, _        = call_service("GET", f"{SEAT_INVENTORY_SERVICE}/inventory/event/{event['eventId']}")
        seats_avail   = sum(1 for s in (inv or {}).get("inventory", []) if s["status"] == "available")
        enriched.append({
            **event,
            "venue": {
                "venueId": venue["venueId"],
                "name": venue["name"],
                "address": venue.get("address"),
            } if venue else None,
            "seatsAvailable": seats_avail,
        })

    return jsonify({"data": {"events": enriched}}), 200


# ── GET /events/<event_id> ────────────────────────────────────────────────────

@bp.get("/events/<event_id>")
def get_event(event_id):
    event_data, err = call_service("GET", f"{EVENT_SERVICE}/events/{event_id}")
    if err == "EVENT_NOT_FOUND":
        return _error("EVENT_NOT_FOUND", "Event not found.", 404)
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not fetch event.", 503)

    venue, _ = call_service("GET", f"{VENUE_SERVICE}/venues/{event_data['venueId']}")

    return jsonify({"data": {**event_data, "venue": venue}}), 200


# ── GET /events/<event_id>/seats ──────────────────────────────────────────────

@bp.get("/events/<event_id>/seats")
def get_seat_map(event_id):
    event_data, err = call_service("GET", f"{EVENT_SERVICE}/events/{event_id}")
    if err:
        return _error("EVENT_NOT_FOUND", "Event not found.", 404)

    inv_data, err = call_service("GET", f"{SEAT_INVENTORY_SERVICE}/inventory/event/{event_id}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not fetch seat map.", 503)

    # Fetch all seats for this venue once and build a lookup map
    venue_id = event_data.get("venueId")
    seat_list, _ = call_service("GET", f"{SEAT_SERVICE}/seats/venue/{venue_id}")
    seat_map = {s["seatId"]: s for s in (seat_list or {}).get("seats", [])}

    event_price = event_data.get("price", 0)
    seats = []
    for s in inv_data.get("inventory", []):
        seat_info = seat_map.get(s.get("seatId"), {})
        seats.append({
            "inventoryId": s["inventoryId"],
            "seatId": s.get("seatId"),
            "status": s["status"],
            "heldUntil": s.get("heldUntil"),
            "rowNumber": seat_info.get("rowNumber"),
            "seatNumber": seat_info.get("seatNumber"),
            "price": event_price,
        })

    return jsonify({"data": {"eventId": event_id, "seats": seats}}), 200


# ── GET /events/<event_id>/seats/<inventory_id> ───────────────────────────────

@bp.get("/events/<event_id>/seats/<inventory_id>")
def get_seat_detail(event_id, inventory_id):
    event_data, err = call_service("GET", f"{EVENT_SERVICE}/events/{event_id}")
    if err:
        return _error("EVENT_NOT_FOUND", "Event not found.", 404)

    # Seat Inventory REST does not expose single-seat lookup — filter from event list
    inv_data, err = call_service("GET", f"{SEAT_INVENTORY_SERVICE}/inventory/event/{event_id}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not fetch seat data.", 503)

    seat = next(
        (s for s in inv_data.get("inventory", []) if s["inventoryId"] == inventory_id),
        None,
    )
    if not seat:
        return _error("SEAT_NOT_FOUND", "Seat not found for this event.", 404)

    venue, _ = call_service("GET", f"{VENUE_SERVICE}/venues/{event_data['venueId']}")

    return jsonify({"data": {
        **seat,
        "event": {
            "eventId": event_data["eventId"],
            "name": event_data["name"],
            "date": event_data["date"],
            "price": event_data["price"],
        },
        "venue": {
            "venueId": venue["venueId"],
            "name": venue["name"],
            "address": venue.get("address"),
        } if venue else None,
    }}), 200
