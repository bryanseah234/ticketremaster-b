"""
Order Model — Order Service
Status: PENDING | CONFIRMED | FAILED | REFUNDED
"""

import uuid
from datetime import datetime, timezone
from db import db


class Order(db.Model):
    __tablename__ = "orders"

    order_id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id = db.Column(db.UUID(as_uuid=True), nullable=False)
    seat_id = db.Column(db.UUID(as_uuid=True), nullable=False)
    event_id = db.Column(db.UUID(as_uuid=True), nullable=False)
    status = db.Column(
        db.Enum("PENDING", "CONFIRMED", "FAILED", "REFUNDED", name="order_status"),
        nullable=False,
        default="PENDING"
    )
    credits_charged  = db.Column(db.Numeric(10, 2), nullable=False)
    verification_sid = db.Column(db.Text, nullable=True)  # SMU API OTP session ID for high-risk purchases
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "order_id":         str(self.order_id),
            "user_id":          str(self.user_id),
            "seat_id":          str(self.seat_id),
            "event_id":         str(self.event_id),
            "status":           self.status,
            "credits_charged":  float(self.credits_charged),
            "verification_sid": self.verification_sid,
            "created_at":       self.created_at.isoformat(),
            "confirmed_at":     self.confirmed_at.isoformat() if self.confirmed_at else None,
        }