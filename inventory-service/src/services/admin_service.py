from src.models.seat import Seat
import uuid
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

def create_seats(session, event_id: str, total_seats: int):
    """Bulk insert seats for an event."""
    try:
        seats = []
        for i in range(total_seats):
            row = str((i // 100) + 1)
            seat_num = (i % 100) + 1
            seats.append(Seat(
                event_id=event_id,
                row_number=row,
                seat_number=seat_num,
                status="AVAILABLE"
            ))
        
        # Insert in chunks of 1000 to be safe
        session.bulk_save_objects(seats)
        session.commit()
        return True, total_seats, None
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error creating seats for event {event_id}: {e}")
        return False, 0, "DB_ERROR"

def get_event_seats_info(session, event_id: str):
    """Retrieve all seats for an event."""
    try:
        seats = session.query(Seat).filter(Seat.event_id == event_id).all()
        return seats, None
    except SQLAlchemyError as e:
        logger.error(f"Error getting seats info for event {event_id}: {e}")
        return None, "DB_ERROR"
