from src.extensions import db
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

class Event(db.Model):
    __tablename__ = 'events'

    event_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    venue_id = db.Column(UUID(as_uuid=True), db.ForeignKey('venues.venue_id'), nullable=False)
    hall_id = db.Column(db.String(20), nullable=False)
    event_date = db.Column(db.DateTime, nullable=False)
    total_seats = db.Column(db.Integer, nullable=False)
    pricing_tiers = db.Column(JSONB, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    venue = db.relationship('Venue', backref=db.backref('events', lazy=True))

    def to_dict(self):
        return {
            'event_id': str(self.event_id),
            'name': self.name,
            'venue': self.venue.to_dict() if self.venue else None,
            'hall_id': self.hall_id,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'total_seats': self.total_seats,
            'pricing_tiers': self.pricing_tiers
        }
