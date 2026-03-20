import uuid
from datetime import UTC, datetime

from app import db


class Venue(db.Model):
    __tablename__ = 'venues'

    venueId = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    address = db.Column(db.String(500), nullable=False)
    postalCode = db.Column(db.String(10), nullable=True)
    coordinates = db.Column(db.String(50), nullable=True)
    isActive = db.Column(db.Boolean, nullable=False, default=True)
    createdAt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'venueId': self.venueId,
            'name': self.name,
            'capacity': self.capacity,
            'address': self.address,
            'postalCode': self.postalCode,
            'coordinates': self.coordinates,
            'isActive': self.isActive,
            'createdAt': self.createdAt.isoformat(),
        }
