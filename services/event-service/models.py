import uuid
from datetime import UTC, datetime

from app import db


class Event(db.Model):
    __tablename__ = 'events'

    eventId = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    venueId = db.Column(db.String(36), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text, nullable=True)
    type = db.Column(db.String(50), nullable=False)
    image = db.Column(db.String(500), nullable=True)
    price = db.Column(db.Float, nullable=False)
    createdAt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def to_dict(self, summary=False):
        """Return event data. If summary=True, exclude detail fields for list view."""
        payload = {
            'eventId': self.eventId,
            'venueId': self.venueId,
            'name': self.name,
            'date': self.date.isoformat(),
            'type': self.type,
            'price': self.price,
            'image': self.image,
        }
        if not summary:
            payload['description'] = self.description
        payload['createdAt'] = self.createdAt.isoformat()
        return payload
