from src.extensions import db
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
import logging

logger = logging.getLogger("event-service")

class Event(db.Model):
    __tablename__ = 'events'

    event_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    venue_id = db.Column(UUID(as_uuid=True), db.ForeignKey('venues.venue_id'), nullable=False)
    hall_id = db.Column(db.String(20), nullable=False)
    event_date = db.Column(db.DateTime, nullable=False)
    total_seats = db.Column(db.Integer, nullable=False)
    pricing_tiers = db.Column(JSONB, nullable=False)
    seat_selection_mode = db.Column(db.String(20), nullable=False, default="SEATMAP")
    seat_config = db.Column(JSONB, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    venue = db.relationship('Venue', backref=db.backref('events', lazy=True))

    def to_dict(self):
        venue_info = None
        if self.venue:
            logger.info(f"DEBUG: self.venue internal: {self.venue}, type: {type(self.venue)}, id: {id(self.venue)}")
            try:
                if hasattr(self.venue, 'to_dict'):
                    venue_info = self.venue.to_dict()
                else:
                    logger.warning(f"DEBUG: self.venue MISSING to_dict. MRO: {type(self.venue).mro()}")
                    # Manual fallback
                    venue_info = {
                        'venue_id': str(self.venue.venue_id),
                        'name': self.venue.name,
                        'address': self.venue.address,
                        'total_halls': getattr(self.venue, 'total_halls', 1)
                    }
            except Exception as e:
                logger.error(f"DEBUG: Failed to serialize venue: {str(e)}")
                venue_info = {"error": "serialization_failed", "msg": str(e)}

        return {
            'event_id': str(self.event_id),
            'name': self.name,
            'venue': venue_info,
            'hall_id': self.hall_id,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'total_seats': self.total_seats,
            'pricing_tiers': self.pricing_tiers,
            'seat_selection_mode': self.seat_selection_mode,
            'seat_config': self.seat_config
        }
