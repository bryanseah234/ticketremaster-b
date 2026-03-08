"""
Marketplace Listing Model — Order Service
Status: ACTIVE | PENDING_TRANSFER | COMPLETED | CANCELLED
"""

import uuid
from datetime import datetime, timezone
from db import db

class MarketplaceListing(db.Model):
    __tablename__ = "marketplace_listings"

    listing_id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    seat_id = db.Column(db.UUID(as_uuid=True), nullable=False)
    seller_user_id = db.Column(db.UUID(as_uuid=True), nullable=False)
    buyer_user_id = db.Column(db.UUID(as_uuid=True), nullable=True)
    escrow_transaction_id = db.Column(db.UUID(as_uuid=True), nullable=True)
    asking_price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(
        db.Enum("ACTIVE", "PENDING_TRANSFER", "COMPLETED", "CANCELLED", name="marketplace_listing_status"),
        nullable=False,
        default="ACTIVE"
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            "listing_id": str(self.listing_id),
            "seat_id": str(self.seat_id),
            "seller_user_id": str(self.seller_user_id),
            "buyer_user_id": str(self.buyer_user_id) if self.buyer_user_id else None,
            "escrow_transaction_id": str(self.escrow_transaction_id) if self.escrow_transaction_id else None,
            "asking_price": float(self.asking_price),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
