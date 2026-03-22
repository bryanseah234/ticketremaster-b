import uuid
from datetime import UTC, datetime

from app import db


class Seat(db.Model):
    __tablename__ = 'seats'
    __table_args__ = (db.UniqueConstraint('venueId', 'seatNumber', name='uq_seats_venue_seat_number'),)

    seatId = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    venueId = db.Column(db.String(36), nullable=False, index=True)
    seatNumber = db.Column(db.String(10), nullable=False)
    rowNumber = db.Column(db.String(5), nullable=False)
    createdAt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'seatId': self.seatId,
            'venueId': self.venueId,
            'seatNumber': self.seatNumber,
            'rowNumber': self.rowNumber,
            'createdAt': self.createdAt.isoformat(),
        }
