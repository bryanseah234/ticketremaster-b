"""
Ticket Verification Orchestrator.
Staff-only. venueId is read from JWT — never from the request body.

Check order (must not be changed):
  1. Look up ticket by QR hash
  2. QR TTL check                    → log expired
  3. Event active check
  4. Seat status = sold check
  5. Ticket status = active check    → log invalid
  6. Duplicate scan check            → log duplicate
  7. Venue match check               → log wrong_venue, return redirect
  8. All pass → mark used, log checked_in
"""
import logging
import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from middleware import require_staff
from service_client import call_service

bp     = Blueprint("verify", __name__)
logger = logging.getLogger(__name__)

TICKET_SERVICE         = os.environ.get("TICKET_SERVICE_URL",          "http://ticket-service:5000")
TICKET_LOG_SERVICE     = os.environ.get("TICKET_LOG_SERVICE_URL",      "http://ticket-log-service:5000")
EVENT_SERVICE          = os.environ.get("EVENT_SERVICE_URL",           "http://event-service:5000")
VENUE_SERVICE          = os.environ.get("VENUE_SERVICE_URL",           "http://venue-service:5000")
SEAT_INV_SERVICE       = os.environ.get("SEAT_INVENTORY_SERVICE_URL",  "http://seat-inventory-service:5000")

QR_TTL_SECONDS = int(os.environ.get("QR_TTL_SECONDS", "60"))


def _error(code, message, status, **extra):
    body = {"error": {"code": code, "message": message}}
    body["error"].update(extra)
    return jsonify(body), status


def _log(ticket_id, staff_id, status):
    call_service("POST", f"{TICKET_LOG_SERVICE}/ticket-logs", json={
        "ticketId": ticket_id,
        "staffId":  staff_id,
        "status":   status,
    })

# ── POST /verify/scan ─────────────────────────────────────────────────────────

@bp.post("/verify/scan")
@require_staff
def scan():
    """
    Scan a QR code to verify and check in a ticket (staff only)
    ---
    tags:
      - Verification
    security:
      - BearerAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [qrHash]
          properties:
            qrHash:
              type: string
              example: a3f9d2e1b8c74f6a91e2d3b4c5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4
    responses:
      200:
        description: Ticket checked in successfully
      400:
        description: QR expired, seat not sold, ticket not active, or wrong venue
      401:
        description: Unauthorized
      403:
        description: Staff role required
      404:
        description: QR hash not found
      409:
        description: Ticket already checked in
    """
    body    = request.get_json(silent=True) or {}
    qr_hash = body.get("qrHash")
    if not qr_hash:
        return _error("VALIDATION_ERROR", "qrHash is required.", 400)

    staff_id       = request.user["userId"]
    staff_venue_id = request.user.get("venueId")   # from JWT only

    # 1. Look up ticket by QR hash
    ticket, err = call_service("GET", f"{TICKET_SERVICE}/tickets/qr/{qr_hash}")
    if err:
        return _error("TICKET_NOT_FOUND", "No ticket matches this QR code.", 404)

    ticket_id = ticket["ticketId"]

    # 2. QR TTL check
    try:
        ts = ticket.get("qrTimestamp", "")
        if ts:
            ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - ts_dt > timedelta(seconds=QR_TTL_SECONDS):
                _log(ticket_id, staff_id, "expired")
                return _error("QR_EXPIRED", "QR code has expired — ask the attendee to refresh.", 400)
    except (ValueError, TypeError):
        _log(ticket_id, staff_id, "expired")
        return _error("QR_EXPIRED", "Could not parse QR timestamp.", 400)

    # 3. Validate event
    event, err = call_service("GET", f"{EVENT_SERVICE}/events/{ticket['eventId']}")
    if err:
        _log(ticket_id, staff_id, "invalid")
        return _error("TICKET_NOT_FOUND", "Associated event not found.", 400)

    # 4. Seat status = sold
    inv_data, _ = call_service("GET", f"{SEAT_INV_SERVICE}/inventory/event/{ticket['eventId']}")
    seat = next(
        (s for s in (inv_data or {}).get("inventory", []) if s["inventoryId"] == ticket["inventoryId"]),
        None,
    )
    if not seat or seat.get("status") != "sold":
        _log(ticket_id, staff_id, "invalid")
        return _error("TICKET_NOT_FOUND", "Seat is not marked as sold.", 400)

    # 5. Ticket status = active
    if ticket["status"] != "active":
        _log(ticket_id, staff_id, "invalid")
        return _error("QR_INVALID", f"Ticket status is '{ticket['status']}' — not valid for entry.", 400)

    # 6. Duplicate scan check
    logs_data, _ = call_service("GET", f"{TICKET_LOG_SERVICE}/ticket-logs/ticket/{ticket_id}")
    already_in   = any(
        log["status"] == "checked_in"
        for log in (logs_data or {}).get("logs", [])
    )
    if already_in:
        _log(ticket_id, staff_id, "duplicate")
        return _error("ALREADY_CHECKED_IN", "This ticket has already been used.", 409)

    # 7. Venue match (venueId from JWT, never from request body)
    if staff_venue_id and ticket.get("venueId") != staff_venue_id:
        correct_venue, _ = call_service("GET", f"{VENUE_SERVICE}/venues/{ticket['venueId']}")
        _log(ticket_id, staff_id, "wrong_venue")
        return _error(
            "WRONG_HALL",
            "This ticket is for a different venue.",
            400,
            correctVenue=correct_venue,
        )

    # 8. All checks passed
    call_service("PATCH", f"{TICKET_SERVICE}/tickets/{ticket_id}", json={"status": "used"})
    _log(ticket_id, staff_id, "checked_in")

    return jsonify({"data": {
        "result":    "SUCCESS",
        "ticketId":  ticket_id,
        "scannedAt": datetime.now(timezone.utc).isoformat(),
        "event": {
            "name": event["name"],
            "date": event["date"],
        },
        "seat": {
            "seatId": seat.get("seatId"),
        },
        "owner": {"userId": ticket["ownerId"]},
    }}), 200

# ── POST /verify/manual ───────────────────────────────────────────────────────

@bp.post("/verify/manual")
@require_staff
def manual_verify():
    """
    Manually verify a ticket by ticket ID (staff only — no QR required)
    ---
    tags:
      - Verification
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
      200:
        description: Ticket checked in successfully
      400:
        description: Ticket not active or wrong venue
      401:
        description: Unauthorized
      403:
        description: Staff role required
      404:
        description: Ticket not found
      409:
        description: Ticket already checked in
    """
    body      = request.get_json(silent=True) or {}
    ticket_id = body.get("ticketId")
    if not ticket_id:
        return _error("VALIDATION_ERROR", "ticketId is required.", 400)

    staff_id       = request.user["userId"]
    staff_venue_id = request.user.get("venueId")   # from JWT only

    # 1. Look up ticket by ID
    ticket, err = call_service("GET", f"{TICKET_SERVICE}/tickets/{ticket_id}")
    if err:
        return _error("TICKET_NOT_FOUND", "No ticket found with that ID.", 404)

    # 2. Validate event
    event, err = call_service("GET", f"{EVENT_SERVICE}/events/{ticket['eventId']}")
    if err:
        _log(ticket_id, staff_id, "invalid")
        return _error("TICKET_NOT_FOUND", "Associated event not found.", 400)

    # 3. Seat status = sold
    inv_data, _ = call_service("GET", f"{SEAT_INV_SERVICE}/inventory/event/{ticket['eventId']}")
    seat = next(
        (s for s in (inv_data or {}).get("inventory", []) if s["inventoryId"] == ticket["inventoryId"]),
        None,
    )
    if not seat or seat.get("status") != "sold":
        _log(ticket_id, staff_id, "invalid")
        return _error("TICKET_NOT_FOUND", "Seat is not marked as sold.", 400)

    # 4. Ticket status = active
    if ticket["status"] != "active":
        _log(ticket_id, staff_id, "invalid")
        return _error("QR_INVALID", f"Ticket status is '{ticket['status']}' — not valid for entry.", 400)

    # 5. Duplicate scan check
    logs_data, _ = call_service("GET", f"{TICKET_LOG_SERVICE}/ticket-logs/ticket/{ticket_id}")
    already_in   = any(
        log["status"] == "checked_in"
        for log in (logs_data or {}).get("logs", [])
    )
    if already_in:
        _log(ticket_id, staff_id, "duplicate")
        return _error("ALREADY_CHECKED_IN", "This ticket has already been used.", 409)

    # 6. Venue match (venueId from JWT, never from request body)
    if staff_venue_id and ticket.get("venueId") != staff_venue_id:
        correct_venue, _ = call_service("GET", f"{VENUE_SERVICE}/venues/{ticket['venueId']}")
        _log(ticket_id, staff_id, "wrong_venue")
        return _error(
            "WRONG_HALL",
            "This ticket is for a different venue.",
            400,
            correctVenue=correct_venue,
        )

    # 7. All checks passed
    call_service("PATCH", f"{TICKET_SERVICE}/tickets/{ticket_id}", json={"status": "used"})
    _log(ticket_id, staff_id, "checked_in")

    return jsonify({"data": {
        "result":    "SUCCESS",
        "ticketId":  ticket_id,
        "scannedAt": datetime.now(timezone.utc).isoformat(),
        "event": {
            "name": event["name"],
            "date": event["date"],
        },
        "seat": {
            "seatId": seat.get("seatId"),
        },
        "owner": {"userId": ticket["ownerId"]},
    }}), 200