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
    params = {k: request.args[k] for k in ("eventId", "page", "limit") if k in request.args}
    listings_data, err = call_service("GET", f"{MARKETPLACE_SERVICE}/listings", params=params)
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve listings.", 503)

    enriched = []
    for listing in listings_data.get("listings", []):
        ticket, _ = call_service("GET", f"{TICKET_SERVICE}/tickets/{listing['ticketId']}")
        event,  _ = call_service("GET", f"{EVENT_SERVICE}/events/{ticket['eventId']}") if ticket else (None, None)
        seller, _ = call_service("GET", f"{USER_SERVICE}/users/{listing['sellerId']}")
        seller_email = seller.get("email") if seller else None
        seller_display = seller_email.split("@")[0] if seller_email else None
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

    return jsonify({"data": {
        "listings":   enriched,
        "pagination": listings_data.get("pagination", {}),
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
