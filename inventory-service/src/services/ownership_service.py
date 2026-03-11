"""
Ownership Service — Inventory Service
Implements ConfirmSeat, UpdateOwner, GetSeatOwner.
"""

from datetime import datetime, timezone
from src.models.seat import Seat


import logging
logger = logging.getLogger(__name__)

def confirm_seat(session, seat_id, user_id):
    """
    Confirm a held seat — set status to SOLD, assign owner_user_id.
    Only succeeds if seat is HELD by the same user.
    """
    seat = session.query(Seat).filter(Seat.seat_id == seat_id).first()

    if seat is None:
        logger.error(f"confirm_seat: Seat {seat_id} not found")
        return False, "SEAT_NOT_FOUND"

    logger.info(f"confirm_seat: seat_id={seat_id}, status={seat.status}, held_by={seat.held_by_user_id}, target_user={user_id}")

    if seat.status != "HELD":
        logger.warning(f"confirm_seat: Seat {seat_id} is not HELD (status={seat.status})")
        return False, "SEAT_NOT_HELD"

    if str(seat.held_by_user_id) != str(user_id):
        logger.warning(f"confirm_seat: Seat {seat_id} held by {seat.held_by_user_id}, but user {user_id} tried to confirm")
        return False, "NOT_HELD_BY_USER"

    seat.status = "SOLD"
    seat.owner_user_id = user_id
    seat.held_by_user_id = None
    seat.held_until = None
    seat.updated_at = datetime.now(timezone.utc)

    logger.info(f"confirm_seat: Seat {seat_id} successfully confirmed for user {user_id}")
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
    For HELD seats, returns the holder as the 'owner' for validation.
    """
    seat = session.query(Seat).filter(Seat.seat_id == seat_id).first()

    if seat is None:
        logger.error(f"get_seat_owner: Seat {seat_id} not found")
        return None, None, "SEAT_NOT_FOUND"

    # If the seat is HELD, we treat the holder as the temporary owner for validation
    if seat.status == "HELD":
        owner_id = str(seat.held_by_user_id) if seat.held_by_user_id else ""
    else:
        owner_id = str(seat.owner_user_id) if seat.owner_user_id else ""
        
    logger.info(f"get_seat_owner: seat_id={seat_id}, status={seat.status}, effective_owner={owner_id}")
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
