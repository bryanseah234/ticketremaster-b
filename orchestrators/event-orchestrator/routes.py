"""
Event Orchestrator — public read-only endpoints.
No JWT required. Aggregates event, venue, and seat-inventory data.
"""
import os

from flask import Blueprint, jsonify, request

from middleware import require_admin
from service_client import call_service

bp = Blueprint("events", __name__)

EVENT_SERVICE          = os.environ.get("EVENT_SERVICE_URL",           "http://event-service:5000")
VENUE_SERVICE          = os.environ.get("VENUE_SERVICE_URL",           "http://venue-service:5000")
SEAT_SERVICE           = os.environ.get("SEAT_SERVICE_URL",            "http://seat-service:5000")
SEAT_INVENTORY_SERVICE = os.environ.get("SEAT_INVENTORY_SERVICE_URL",  "http://seat-inventory-service:5000")
TICKET_SERVICE         = os.environ.get("TICKET_SERVICE_URL",          "http://ticket-service:5000")
USER_SERVICE           = os.environ.get("USER_SERVICE_URL",            "http://user-service:5000")


def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


# ── GET /venues ────────────────────────────────────────────────────────────────

@bp.get("/venues")
def list_venues():
    """
    Get all active venues (read-only)
    ---
    tags:
      - Venues
    responses:
      200:
        description: List of active venues
      503:
        description: Venue service unavailable
    """
    venues_data, err = call_service("GET", f"{VENUE_SERVICE}/venues")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not fetch venues.", 503)
    
    return jsonify(venues_data), 200


# ── GET /events ───────────────────────────────────────────────────────────────

@bp.get("/events")
def list_events():
    """
    List all events enriched with venue and seat availability
    ---
    tags:
      - Events
    parameters:
      - in: query
        name: type
        type: string
        description: "Filter by event type (e.g. concert, orchestra, sports)"
      - in: query
        name: page
        type: integer
        description: "Page number (default: 1)"
      - in: query
        name: limit
        type: integer
        description: "Items per page (default: 20, max: 100)"
    responses:
      200:
        description: List of events with venue and seatsAvailable
      503:
        description: Event service unavailable
    """
    # Parse and validate pagination parameters
    page = request.args.get("page", default=1, type=int)
    limit = request.args.get("limit", default=20, type=int)
    
    if page < 1:
        return _error("VALIDATION_ERROR", "page must be an integer greater than or equal to 1.", 400)
    if limit < 1:
        return _error("VALIDATION_ERROR", "limit must be an integer greater than or equal to 1.", 400)
    if limit > 100:
        limit = 100
    
    params = {k: v for k, v in request.args.items() if k in ("type",)}
    params["page"] = page
    params["limit"] = limit
    
    events_data, err = call_service("GET", f"{EVENT_SERVICE}/events", params=params)
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not fetch events.", 503)

    events_list = events_data.get("events", []) if isinstance(events_data, dict) else []
    if events_list:
        # Validate events_list contains dictionaries
        events_list = [e for e in events_list if isinstance(e, dict)]
        enriched = []
        for event in events_list:
            venue = None
            if event.get("venueId"):
                venue, _ = call_service("GET", f"{VENUE_SERVICE}/venues/{event['venueId']}")
            inv, _ = call_service("GET", f"{SEAT_INVENTORY_SERVICE}/inventory/event/{event.get('eventId')}")
            inv = inv or {}
            seats_avail = sum(1 for s in inv.get("inventory", []) if isinstance(s, dict) and s.get("status") == "available")
            enriched.append({
                **event,
                "venue": {
                    "venueId": venue["venueId"],
                    "name": venue["name"],
                    "address": venue.get("address"),
                } if venue else None,
                "seatsAvailable": seats_avail,
            })
    else:
        enriched = []

    return jsonify({"data": {
        "events": enriched,
        "pagination": events_data.get("pagination", {
            "page": page,
            "limit": limit,
            "total": len(enriched),
        }),
    }}), 200


# ── GET /events/<event_id> ────────────────────────────────────────────────────

@bp.get("/events/<event_id>")
def get_event(event_id):
    """
    Get a single event with full venue details
    ---
    tags:
      - Events
    parameters:
      - in: path
        name: event_id
        required: true
        type: string
        example: evt_001
    responses:
      200:
        description: Event with venue details
      404:
        description: Event not found
    """
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
    """
    Get the seat map for an event
    ---
    tags:
      - Events
    parameters:
      - in: path
        name: event_id
        required: true
        type: string
        example: evt_001
    responses:
      200:
        description: Seat map with status for each seat (available, held, sold)
      404:
        description: Event not found
    """
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
    """
    Get details for a single seat including event and venue info
    ---
    tags:
      - Events
    parameters:
      - in: path
        name: event_id
        required: true
        type: string
        example: evt_001
      - in: path
        name: inventory_id
        required: true
        type: string
        example: inv_001
    responses:
      200:
        description: Seat detail with event and venue
      404:
        description: Event or seat not found
    """
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


# ── GET /admin/events/<event_id>/dashboard ───────────────────────────────────

@bp.get("/admin/events/<event_id>/dashboard")
@require_admin
def get_event_dashboard(event_id):
    """
    Admin: aggregate inventory, revenue, and attendee list for an event
    ---
    tags:
      - Admin
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: event_id
        required: true
        type: string
    responses:
      200:
        description: Dashboard stats and attendee list
      401:
        description: Unauthorized
      403:
        description: Admin role required
      404:
        description: Event not found
    """
    event, err = call_service("GET", f"{EVENT_SERVICE}/events/{event_id}")
    if err:
        return _error("EVENT_NOT_FOUND", "Event not found.", 404)

    inv_data, err = call_service("GET", f"{SEAT_INVENTORY_SERVICE}/inventory/event/{event_id}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not fetch inventory data.", 503)

    inventory = inv_data.get("inventory", [])
    total_seats = len(inventory)
    sold_inventory = [s for s in inventory if s.get("status") == "sold"]

    tickets_data, _ = call_service("GET", f"{TICKET_SERVICE}/tickets/event/{event_id}")
    tickets = tickets_data.get("tickets", []) if tickets_data else []

    revenue = sum(t.get("price", 0) for t in tickets)
    inv_to_ticket = {t["inventoryId"]: t for t in tickets if t.get("inventoryId")}

    seat_list, _ = call_service("GET", f"{SEAT_SERVICE}/seats/venue/{event.get('venueId', '')}")
    seat_map = {s["seatId"]: s for s in (seat_list or {}).get("seats", [])}

    attendees = []
    for inv_item in sold_inventory:
        seat_id = inv_item.get("seatId", "")
        seat_info = seat_map.get(seat_id, {})
        ticket = inv_to_ticket.get(inv_item.get("inventoryId", ""))
        email = ""
        if ticket:
            user, _ = call_service("GET", f"{USER_SERVICE}/users/{ticket['ownerId']}")
            email = user.get("email", "") if user else ""
        attendees.append({
            "seatId": seat_id,
            "rowNumber": seat_info.get("rowNumber"),
            "seatNumber": seat_info.get("seatNumber"),
            "email": email,
        })

    return jsonify({"data": {
        "stats": {
            "seatsSold": len(sold_inventory),
            "totalSeats": total_seats,
            "revenue": revenue,
        },
        "attendees": attendees,
    }}), 200


# ── POST /admin/events ────────────────────────────────────────────────────────

@bp.post("/admin/events")
@require_admin
def create_event_admin():
    """
    Admin endpoint: create event and auto-populate seat inventory
    ---
    tags:
      - Admin
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - name
              - type
              - venueId
              - event_date
              - pricing_tiers
            properties:
              name:
                type: string
              description:
                type: string
              type:
                type: string
              venueId:
                type: string
              venue:
                type: object
              event_date:
                type: string
              end_date:
                type: string
              pricing_tiers:
                type: object
              total_seats:
                type: integer
    responses:
      201:
        description: Event created and seats provisioned
      400:
        description: Validation error
      401:
        description: Missing or invalid token
      403:
        description: Admin role required
      503:
        description: Service unavailable
    """
    data = request.get_json(silent=True) or {}
    venue_id = data.get("venueId") or data.get("venue_id")
    event_date = data.get("event_date")
    
    if not all([data.get("name"), data.get("type"), venue_id, event_date]):
        return _error("VALIDATION_ERROR", "Missing required fields: name, type, venueId, event_date", 400)
    
    # Get venue to verify it exists
    venue, err = call_service("GET", f"{VENUE_SERVICE}/venues/{venue_id}")
    if err or not venue:
        return _error("VENUE_NOT_FOUND", f"Venue {venue_id} not found.", 404)
    
    # Create event
    event_payload = {
        "name": data["name"],
        "type": data["type"],
        "venueId": venue_id,
        "date": event_date,
        "price": list(data.get("pricing_tiers", {}).values())[0] if data.get("pricing_tiers") else 0,
        "description": data.get("description", ""),
        "image": data.get("image"),
    }
    
    event, err = call_service("POST", f"{EVENT_SERVICE}/events", json=event_payload)
    if err:
        return _error("EVENT_SERVICE_ERROR", "Failed to create event.", 503)
    
    event_id = event.get("eventId")
    
    # Get all seats for this venue
    seats, err = call_service("GET", f"{SEAT_SERVICE}/seats/venue/{venue_id}")
    if err or not seats:
        return _error("SEAT_SERVICE_ERROR", "Failed to fetch seat data.", 503)
    
    seat_list = seats.get("seats", [])
    seats_created = len(seat_list)
    
    # Populate seat inventory for this event
    inventory_payload = {
        "eventId": event_id,
        "seats": [
            {
                "seatId": seat["seatId"],
                "status": "available",
            }
            for seat in seat_list
        ],
    }
    
    inv, err = call_service("POST", f"{SEAT_INVENTORY_SERVICE}/inventory/batch", json=inventory_payload)
    if err:
        return _error("INVENTORY_ERROR", "Failed to create seat inventory.", 503)
    
    return jsonify({
        "data": {
            "eventId": event_id,
            "seatsCreated": seats_created,
        }
    }), 201
