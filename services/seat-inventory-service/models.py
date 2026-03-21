import uuid
from datetime import UTC, datetime

from app import db


class SeatInventory(db.Model):
    __tablename__ = 'seat_inventory'

    inventoryId = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    eventId = db.Column(db.String(36), nullable=False, index=True)
    seatId = db.Column(db.String(36), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='available', index=True)
    heldByUserId = db.Column(db.String(36), nullable=True)
    holdToken = db.Column(db.String(64), nullable=True, index=True)
    heldUntil = db.Column(db.DateTime, nullable=True)
    createdAt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updatedAt = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        db.UniqueConstraint('eventId', 'seatId', name='uq_seat_inventory_event_seat'),
    )

    def to_dict(self, include_internal=False):
        return {
            'inventoryId': self.inventoryId,
            'eventId': self.eventId,
            'seatId': self.seatId,
            'status': self.status,
            **({'heldByUserId': self.heldByUserId, 'holdToken': self.holdToken} if include_internal else {}),
            'heldUntil': self.heldUntil.isoformat() if self.heldUntil else None,
            'createdAt': self.createdAt.isoformat(),
            'updatedAt': self.updatedAt.isoformat(),
        }
