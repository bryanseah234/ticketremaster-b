import uuid
from datetime import UTC, datetime

from app import db


class Ticket(db.Model):
    __tablename__ = 'tickets'

    ticketId = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    inventoryId = db.Column(db.String(36), nullable=False)
    ownerId = db.Column(db.String(36), nullable=False, index=True)
    venueId = db.Column(db.String(36), nullable=False)
    eventId = db.Column(db.String(36), nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')
    qrHash = db.Column(db.String(64), nullable=True, index=True, unique=True)
    qrTimestamp = db.Column(db.DateTime, nullable=True)
    createdAt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'ticketId': self.ticketId,
            'inventoryId': self.inventoryId,
            'ownerId': self.ownerId,
            'venueId': self.venueId,
            'eventId': self.eventId,
            'price': self.price,
            'status': self.status,
            'qrHash': self.qrHash,
            'qrTimestamp': self.qrTimestamp.isoformat() if self.qrTimestamp else None,
            'createdAt': self.createdAt.isoformat(),
        }
