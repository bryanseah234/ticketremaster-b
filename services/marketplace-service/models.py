import uuid
from datetime import UTC, datetime

from app import db


class Listing(db.Model):
    __tablename__ = 'listings'

    listingId = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticketId = db.Column(db.String(36), nullable=False, index=True)
    sellerId = db.Column(db.String(36), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')
    createdAt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'listingId': self.listingId,
            'ticketId': self.ticketId,
            'sellerId': self.sellerId,
            'price': self.price,
            'status': self.status,
            'createdAt': self.createdAt.isoformat(),
        }
