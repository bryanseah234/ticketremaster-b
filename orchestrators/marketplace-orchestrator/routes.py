"""
Marketplace Orchestrator.
GET /marketplace is public (no JWT) — browse listings.
POST /marketplace/list and DELETE /marketplace/<id> require JWT.
"""
import os

from flask import Blueprint, jsonify, request

from middleware import require_auth
from service_client import call_service

bp = Blueprint("marketplace", __name__)

TICKET_SERVICE      = os.environ.get("TICKET_SERVICE_URL",      "http://ticket-service:5000")
MARKETPLACE_SERVICE = os.environ.get("MARKETPLACE_SERVICE_URL", "http://marketplace-service:5000")
EVENT_SERVICE       = os.environ.get("EVENT_SERVICE_URL",       "http://event-service:5000")
SEAT_INV_SERVICE    = os.environ.get("SEAT_INVENTORY_SERVICE_URL", "http://seat-inventory-service:5000")
USER_SERVICE        = os.environ.get("USER_SERVICE_URL",        "http://user-service:5000")


def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def _parse_pagination_args():
    page = request.args.get("page", default=1, type=int)
    limit = request.args.get("limit", default=20, type=int)
    if page is None or page < 1:
        return None, None, _error("VALIDATION_ERROR", "page must be an integer greater than or equal to 1.", 400)
    if limit is None or limit < 1:
        return None, None, _error("VALIDATION_ERROR", "limit must be an integer greater than or equal to 1.", 400)
    return page, min(limit, 100), None


# ── GET /marketplace ──────────────────────────────────────────────────────────

@bp.get("/marketplace")
def browse():
    """
    Browse all active marketplace listings
    ---
    tags:
      - Marketplace
    parameters:
      - in: query
        name: eventId
        type: string
        description: Filter listings by event
        example: evt_001
    responses:
      200:
        description: List of active listings enriched with event details
    """
    page, limit, pagination_error = _parse_pagination_args()
    if pagination_error:
        return pagination_error

    event_id = request.args.get("eventId")
    upstream_params = {"page": page, "limit": limit} if not event_id else None
    listings_data, err = call_service("GET", f"{MARKETPLACE_SERVICE}/listings", params=upstream_params)
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve listings.", 503)

    listings_list = listings_data.get("listings", []) if isinstance(listings_data, dict) else []
    
    if listings_list:
        # Validate listings_list contains dictionaries
        listings_list = [l for l in listings_list if isinstance(l, dict)]
        
        # Collect unique IDs for batch fetching
        ticket_ids = list(set(listing['ticketId'] for listing in listings_list if 'ticketId' in listing))
        seller_ids = list(set(listing['sellerId'] for listing in listings_list if 'sellerId' in listing))
        
        # Batch fetch all tickets
        tickets_map = {}
        for ticket_id in ticket_ids:
            ticket, _ = call_service("GET", f"{TICKET_SERVICE}/tickets/{ticket_id}")
            if ticket and isinstance(ticket, dict):
                tickets_map[ticket_id] = ticket
        
        # Collect unique event IDs from tickets
        event_ids = list(set(ticket['eventId'] for ticket in tickets_map.values() if isinstance(ticket, dict) and 'eventId' in ticket))
        
        # Batch fetch all events
        events_map = {}
        for event_id in event_ids:
            event, _ = call_service("GET", f"{EVENT_SERVICE}/events/{event_id}")
            if event and isinstance(event, dict):
                events_map[event_id] = event
        
        # Batch fetch all sellers
        sellers_map = {}
        for seller_id in seller_ids:
            seller, _ = call_service("GET", f"{USER_SERVICE}/users/{seller_id}")
            if seller and isinstance(seller, dict):
                sellers_map[seller_id] = seller
        
        # Enrich listings with batched data
        enriched = []
        for listing in listings_list:
            ticket = tickets_map.get(listing['ticketId'])
            event = events_map.get(ticket['eventId']) if ticket and isinstance(ticket, dict) and 'eventId' in ticket else None
            seller = sellers_map.get(listing['sellerId'])
            seller_email = seller.get("email") if seller else None
            seller_display = seller_email.split("@")[0] if seller_email else None
            
            # Apply eventId filter if specified
            if event_id and (not event or str(event.get("eventId")) != str(event_id)):
                continue
            
            enriched.append({
                "listingId":   listing["listingId"],
                "ticketId":    listing["ticketId"],
                "sellerId":    listing["sellerId"],
                "sellerName":  seller_display,
                "price":       listing["price"],
                "status":      listing["status"],
                "createdAt":   listing["createdAt"],
                "event": {
                    "eventId": event["eventId"],
                    "name":    event["name"],
                    "date":    event["date"],
                } if event else None,
            })
    else:
        enriched = []

    if event_id:
        total = len(enriched)
        start = (page - 1) * limit
        enriched = enriched[start:start + limit]
        pagination = {
            "page": page,
            "limit": limit,
            "total": total,
        }
    else:
        pagination = listings_data.get("pagination", {
            "page": page,
            "limit": limit,
            "total": len(enriched),
        })

    return jsonify({"data": {
        "listings":   enriched,
        "pagination": pagination,
    }}), 200


# ── POST /marketplace/list ────────────────────────────────────────────────────

@bp.post("/marketplace/list")
@require_auth
def list_ticket():
    """
    List a ticket for sale on the marketplace
    ---
    tags:
      - Marketplace
    security:
      - BearerAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [ticketId]
          properties:
            ticketId:
              type: string
              example: tkt_001
    responses:
      201:
        description: Listing created — ticket status set to listed
      400:
        description: Ticket not eligible for listing
      401:
        description: Unauthorized
      403:
        description: You do not own this ticket
      404:
        description: Ticket not found
    """
    user_id = request.user["userId"]
    body    = request.get_json(silent=True) or {}

    if not body.get("ticketId"):
        return _error("VALIDATION_ERROR", "ticketId is required.", 400)

    ticket_id = body["ticketId"]

    ticket, err = call_service("GET", f"{TICKET_SERVICE}/tickets/{ticket_id}")
    if err == "TICKET_NOT_FOUND":
        return _error("TICKET_NOT_FOUND", "Ticket not found.", 404)
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve ticket.", 503)

    if ticket["ownerId"] != user_id:
        return _error("AUTH_FORBIDDEN", "You do not own this ticket.", 403)

    if ticket["status"] != "active":
        return _error("TICKET_NOT_FOUND", f"Ticket status is '{ticket['status']}' — cannot be listed.", 400)

    # Set ticket to listed
    _, err = call_service("PATCH", f"{TICKET_SERVICE}/tickets/{ticket_id}", json={"status": "listed"})
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not update ticket status.", 503)

    # Create listing
    listing_data, err = call_service("POST", f"{MARKETPLACE_SERVICE}/listings", json={
        "ticketId": ticket_id,
        "sellerId": user_id,
        "price":    body.get("price") or ticket["price"],
    })
    if err:
        # Compensate — revert ticket status
        call_service("PATCH", f"{TICKET_SERVICE}/tickets/{ticket_id}", json={"status": "active"})
        return _error("INTERNAL_ERROR", "Could not create listing.", 500)

    return jsonify({"data": listing_data}), 201


# ── DELETE /marketplace/<listing_id> ─────────────────────────────────────────

@bp.delete("/marketplace/<listing_id>")
@require_auth
def delist(listing_id):
    """
    Cancel a marketplace listing and revert ticket to active
    ---
    tags:
      - Marketplace
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: listing_id
        required: true
        type: string
        example: lst_001
    responses:
      200:
        description: Listing cancelled — ticket reverted to active
      400:
        description: Listing is not active
      401:
        description: Unauthorized
      403:
        description: You are not the seller
      404:
        description: Listing not found
    """
    user_id = request.user["userId"]

    listing, err = call_service("GET", f"{MARKETPLACE_SERVICE}/listings/{listing_id}")
    if err == "LISTING_NOT_FOUND":
        return _error("LISTING_NOT_FOUND", "Listing not found.", 404)
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve listing.", 503)

    if listing["sellerId"] != user_id:
        return _error("AUTH_FORBIDDEN", "You are not the seller of this listing.", 403)

    if listing["status"] != "active":
        return _error("LISTING_NOT_FOUND", "Listing is not active.", 400)

    _, err = call_service("PATCH", f"{MARKETPLACE_SERVICE}/listings/{listing_id}", json={"status": "cancelled"})
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not cancel listing.", 503)

    # Revert ticket to active
    call_service("PATCH", f"{TICKET_SERVICE}/tickets/{listing['ticketId']}", json={"status": "active"})

    return jsonify({"data": {"listingId": listing_id, "status": "cancelled"}}), 200
