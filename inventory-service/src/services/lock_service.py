"""
Lock Service — Inventory Service
Implements ReserveSeat (SELECT FOR UPDATE NOWAIT) and ReleaseSeat.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from src.models.seat import Seat

# Hold duration: 5 minutes
HOLD_DURATION_SECONDS = 300


def reserve_seat(session, seat_id, user_id):
    """
    Reserve a seat using SELECT FOR UPDATE NOWAIT.
    Sets status to HELD, held_by_user_id, held_until.
    Returns (success, held_until_iso) or raises on lock failure.
    """
    try:
        seat = (
            session.query(Seat)
            .filter(Seat.seat_id == seat_id)
            .with_for_update(nowait=True)
            .first()
        )
    except OperationalError:
        # Another transaction holds the lock — seat is being reserved by someone else
        session.rollback()
        return False, None, "SEAT_LOCKED"

    if seat is None:
        return False, None, "SEAT_NOT_FOUND"

    if seat.status != "AVAILABLE":
        return False, None, "SEAT_UNAVAILABLE"

    now = datetime.now(timezone.utc)
    held_until = now + timedelta(seconds=HOLD_DURATION_SECONDS)

    seat.status = "HELD"
    seat.held_by_user_id = user_id
    seat.held_until = held_until
    seat.updated_at = now

    return True, held_until.isoformat(), None


def release_seat(session, seat_id):
    """
    Release a held seat — set status back to AVAILABLE, clear hold fields.
    Returns success boolean.
    """
    seat = session.query(Seat).filter(Seat.seat_id == seat_id).first()

    if seat is None:
        return False, "SEAT_NOT_FOUND"

    # Only release if currently HELD (don't release SOLD seats)
    if seat.status not in ("HELD", "AVAILABLE"):
        return False, "INVALID_STATE"

    seat.status = "AVAILABLE"
    seat.held_by_user_id = None
    seat.held_until = None
    seat.updated_at = datetime.now(timezone.utc)

    return True, None
