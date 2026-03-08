"""
Ownership Service — Inventory Service
Implements ConfirmSeat, UpdateOwner, GetSeatOwner.
"""

from datetime import datetime, timezone
from src.models.seat import Seat


def confirm_seat(session, seat_id, user_id):
    """
    Confirm a held seat — set status to SOLD, assign owner_user_id.
    Only succeeds if seat is HELD by the same user.
    """
    seat = session.query(Seat).filter(Seat.seat_id == seat_id).first()

    if seat is None:
        return False, "SEAT_NOT_FOUND"

    if seat.status != "HELD":
        return False, "SEAT_NOT_HELD"

    if str(seat.held_by_user_id) != str(user_id):
        return False, "NOT_HELD_BY_USER"

    seat.status = "SOLD"
    seat.owner_user_id = user_id
    seat.held_by_user_id = None
    seat.held_until = None
    seat.updated_at = datetime.now(timezone.utc)

    return True, None


def update_owner(session, seat_id, new_owner_id):
    """
    Transfer seat ownership — used for P2P transfers.
    Only succeeds if seat status is SOLD.
    """
    seat = session.query(Seat).filter(Seat.seat_id == seat_id).first()

    if seat is None:
        return False, "SEAT_NOT_FOUND"

    if seat.status != "SOLD":
        return False, "SEAT_NOT_SOLD"

    seat.owner_user_id = new_owner_id
    seat.updated_at = datetime.now(timezone.utc)

    return True, None


def get_seat_owner(session, seat_id):
    """
    Get seat owner and status — read-only query for transfer validation.
    """
    seat = session.query(Seat).filter(Seat.seat_id == seat_id).first()

    if seat is None:
        return None, None, "SEAT_NOT_FOUND"

    owner_id = str(seat.owner_user_id) if seat.owner_user_id else ""
    return owner_id, seat.status, None


def list_seat(session, seat_id, seller_user_id):
    """
    Mark a seat as LISTED for resale.
    Only succeeds if seat status is SOLD and seller_user_id matches owner.
    """
    seat = session.query(Seat).filter(Seat.seat_id == seat_id).first()

    if seat is None:
        return False, "SEAT_NOT_FOUND"

    if seat.status != "SOLD":
        return False, "SEAT_NOT_SOLD"

    if str(seat.owner_user_id) != str(seller_user_id):
        return False, "NOT_SEAT_OWNER"

    seat.status = "LISTED"
    seat.updated_at = datetime.now(timezone.utc)

    return True, None
