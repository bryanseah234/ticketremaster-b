"""
QR Orchestrator.
Generates a fresh encrypted QR payload on every open.
TTL enforcement is done at scan time by ticket-verification-orchestrator.
"""
import hashlib
import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from middleware import require_auth
from service_client import call_service

bp = Blueprint("tickets_qr", __name__)

TICKET_SERVICE         = os.environ.get("TICKET_SERVICE_URL",          "http://ticket-service:5000")
EVENT_SERVICE          = os.environ.get("EVENT_SERVICE_URL",            "http://event-service:5000")
VENUE_SERVICE          = os.environ.get("VENUE_SERVICE_URL",            "http://venue-service:5000")
SEAT_INVENTORY_SERVICE = os.environ.get("SEAT_INVENTORY_SERVICE_URL",   "http://seat-inventory-service:5000")

QR_TTL_SECONDS = int(os.environ.get("QR_TTL_SECONDS", "60"))


def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def _generate_qr(ticket_id, user_id, event_id, venue_id):
    """
    SHA-256 hash of ticketId|userId|eventId|venueId|generatedAt|QR_SECRET.
    Matches the QR encryption skill pattern — includes ownership fields so
    ticket-verification-orchestrator can validate owner and venue from the hash lookup.
    """
    generated_at = datetime.now(timezone.utc).isoformat()
    raw = f"{ticket_id}|{user_id}|{event_id}|{venue_id}|{generated_at}|{os.environ['QR_SECRET']}"
    qr_hash = hashlib.sha256(raw.encode()).hexdigest()
    return qr_hash, generated_at


# ── GET /tickets ──────────────────────────────────────────────────────────────

@bp.get("/tickets")
@require_auth
def list_tickets():
    """
    List all tickets owned by the authenticated user
    ---
    tags:
      - Tickets
    security:
      - BearerAuth: []
    responses:
      200:
        description: List of tickets enriched with event and venue details
      401:
        description: Unauthorized
    """
    user_id = request.user["userId"]
    data, err = call_service("GET", f"{TICKET_SERVICE}/tickets/owner/{user_id}")
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve tickets.", 503)

    enriched = []
    for t in data.get("tickets", []):
        event, _ = call_service("GET", f"{EVENT_SERVICE}/events/{t['eventId']}")
        venue, _ = call_service("GET", f"{VENUE_SERVICE}/venues/{t['venueId']}")
        enriched.append({
            "ticketId":    t["ticketId"],
            "status":      t["status"],
            "price":       t["price"],
            "createdAt":   t["createdAt"],
            "event": {
                "eventId": event["eventId"],
                "name":    event["name"],
                "date":    event["date"],
            } if event else None,
            "venue": {
                "venueId": venue["venueId"],
                "name":    venue["name"],
            } if venue else None,
        })

    return jsonify({"data": {"tickets": enriched}}), 200


# ── GET /tickets/<ticket_id>/qr ───────────────────────────────────────────────

@bp.get("/tickets/<ticket_id>/qr")
@require_auth
def get_qr(ticket_id):
    """
    Generate a fresh QR hash for a ticket (60-second TTL)
    ---
    tags:
      - Tickets
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: ticket_id
        required: true
        type: string
        example: tkt_001
    responses:
      200:
        description: QR hash and expiry timestamp
      400:
        description: Ticket not active (listed or used)
      401:
        description: Unauthorized
      403:
        description: You do not own this ticket
      404:
        description: Ticket not found
    """
    user_id = request.user["userId"]

    ticket, err = call_service("GET", f"{TICKET_SERVICE}/tickets/{ticket_id}")
    if err == "TICKET_NOT_FOUND":
        return _error("TICKET_NOT_FOUND", "Ticket not found.", 404)
    if err:
        return _error("SERVICE_UNAVAILABLE", "Could not retrieve ticket.", 503)

    if ticket["ownerId"] != user_id:
        return _error("AUTH_FORBIDDEN", "You do not own this ticket.", 403)

    if ticket["status"] != "active":
        return _error("QR_INVALID", f"Ticket status is '{ticket['status']}' — QR cannot be generated.", 400)

    qr_hash, generated_at = _generate_qr(
        ticket_id, user_id, ticket["eventId"], ticket["venueId"]
    )

    # Persist new hash and timestamp on ticket record
    _, err = call_service("PATCH", f"{TICKET_SERVICE}/tickets/{ticket_id}", json={
        "qrHash":      qr_hash,
        "qrTimestamp": generated_at,
    })
    if err:
        return _error("INTERNAL_ERROR", "Could not update QR on ticket.", 500)

    expires_at = (datetime.fromisoformat(generated_at) + timedelta(seconds=QR_TTL_SECONDS)).isoformat()

    event, _ = call_service("GET", f"{EVENT_SERVICE}/events/{ticket['eventId']}")
    venue, _ = call_service("GET", f"{VENUE_SERVICE}/venues/{ticket['venueId']}")

    return jsonify({"data": {
        "ticketId":    ticket_id,
        "qrHash":      qr_hash,
        "generatedAt": generated_at,
        "expiresAt":   expires_at,
        "event": {
            "name": event["name"],
            "date": event["date"],
        } if event else None,
        "venue": {
            "name":    venue["name"],
            "address": venue.get("address"),
        } if venue else None,
    }}), 200
