"""
Transfer Model — Order Service
Status: INITIATED | PENDING_OTP | COMPLETED | DISPUTED | REVERSED | FAILED
"""
import uuid
from datetime import datetime, timezone
from db import db


class Transfer(db.Model):
    __tablename__ = "transfers"

    transfer_id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    seat_id = db.Column(db.UUID(as_uuid=True), nullable=False)
    seller_user_id = db.Column(db.UUID(as_uuid=True), nullable=False)
    buyer_user_id = db.Column(db.UUID(as_uuid=True), nullable=False)
    initiated_by = db.Column(
        db.Enum("SELLER", "BUYER", name="transfer_initiator"),
        nullable=False
    )
    status = db.Column(
        db.Enum("INITIATED", "PENDING_OTP", "COMPLETED", "DISPUTED", "REVERSED", "FAILED",
                name="transfer_status"),
        nullable=False,
        default="INITIATED"
    )
    seller_otp_verified = db.Column(db.Boolean, default=False)
    buyer_otp_verified = db.Column(db.Boolean, default=False)
    seller_verification_sid = db.Column(db.Text, nullable=True)  # SMU API session ID for seller
    buyer_verification_sid = db.Column(db.Text, nullable=True)   # SMU API session ID for buyer
    credits_amount = db.Column(db.Numeric(10, 2), nullable=True)
    dispute_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "transfer_id":             str(self.transfer_id),
            "seat_id":                 str(self.seat_id),
            "seller_user_id":          str(self.seller_user_id),
            "buyer_user_id":           str(self.buyer_user_id),
            "initiated_by":            self.initiated_by,
            "status":                  self.status,
            "seller_otp_verified":     self.seller_otp_verified,
            "buyer_otp_verified":      self.buyer_otp_verified,
            "seller_verification_sid": self.seller_verification_sid,
            "buyer_verification_sid":  self.buyer_verification_sid,
            "credits_amount":          float(self.credits_amount) if self.credits_amount else None,
            "dispute_reason":          self.dispute_reason,
            "created_at":              self.created_at.isoformat(),
            "completed_at":            self.completed_at.isoformat() if self.completed_at else None,
        }