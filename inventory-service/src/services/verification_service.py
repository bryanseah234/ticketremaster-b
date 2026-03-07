"""
Verification Service — Inventory Service
Implements VerifyTicket (read-only) and MarkCheckedIn (writes entry_logs).
"""

import uuid
from datetime import datetime, timezone
from src.models.seat import Seat
from src.models.entry_log import EntryLog


def verify_ticket(session, seat_id):
    """
    Read-only verification — return seat status, owner, and event_id.
    Used by Orchestrator for ticket verification flow.
    """
    seat = session.query(Seat).filter(Seat.seat_id == seat_id).first()

    if seat is None:
        return None, None, None, "SEAT_NOT_FOUND"

    owner_id = str(seat.owner_user_id) if seat.owner_user_id else ""
    event_id = str(seat.event_id)

    return seat.status, owner_id, event_id, None


def mark_checked_in(session, seat_id, hall_id_presented=None, staff_id=None):
    """
    Mark a seat as CHECKED_IN and write an entry_log record.
    Only succeeds if seat is currently SOLD.
    """
    seat = session.query(Seat).filter(Seat.seat_id == seat_id).first()

    if seat is None:
        # Write a NOT_FOUND entry log
        log = EntryLog(
            log_id=uuid.uuid4(),
            seat_id=seat_id,
            scanned_by_staff_id=staff_id,
            result="NOT_FOUND",
            hall_id_presented=hall_id_presented,
        )
        session.add(log)
        return False, "SEAT_NOT_FOUND"

    # Determine the expected hall — we don't have hall_id on seat directly,
    # but we can check status-based rules
    if seat.status == "CHECKED_IN":
        # Duplicate check-in attempt
        log = EntryLog(
            log_id=uuid.uuid4(),
            seat_id=seat_id,
            scanned_by_staff_id=staff_id,
            result="DUPLICATE",
            hall_id_presented=hall_id_presented,
        )
        session.add(log)
        return False, "ALREADY_CHECKED_IN"

    if seat.status != "SOLD":
        # Seat not paid for / not in correct state
        result = "UNPAID" if seat.status in ("AVAILABLE", "HELD") else "EXPIRED"
        log = EntryLog(
            log_id=uuid.uuid4(),
            seat_id=seat_id,
            scanned_by_staff_id=staff_id,
            result=result,
            hall_id_presented=hall_id_presented,
        )
        session.add(log)
        return False, "SEAT_NOT_SOLD"

    # Success — mark as checked in
    seat.status = "CHECKED_IN"
    seat.updated_at = datetime.now(timezone.utc)

    log = EntryLog(
        log_id=uuid.uuid4(),
        seat_id=seat_id,
        scanned_by_staff_id=staff_id,
        result="SUCCESS",
        hall_id_presented=hall_id_presented,
    )
    session.add(log)

    return True, None
