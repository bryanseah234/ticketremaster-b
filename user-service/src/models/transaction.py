"""
Transaction Model — User Service
Tracks credit balances changes (Escrow, Transfers, Refunds).
"""

import uuid
from datetime import datetime, timezone
from src.extensions import db

class CreditTransaction(db.Model):
    __tablename__ = "credits_transactions"

    transaction_id = db.Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("users.user_id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    type = db.Column(
        db.Enum('DEPOSIT', 'WITHDRAWAL', 'TRANSFER', 'ESCROW_HOLD', 'ESCROW_RELEASE', 'REFUND', name='transaction_type'),
        nullable=False
    )
    status = db.Column(
        db.Enum('PENDING', 'COMPLETED', 'FAILED', 'CANCELLED', name='transaction_status'),
        nullable=False,
        default='PENDING'
    )
    reference_id = db.Column(db.UUID(as_uuid=True), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "transaction_id": str(self.transaction_id),
            "user_id": str(self.user_id),
            "amount": float(self.amount),
            "type": self.type,
            "status": self.status,
            "reference_id": str(self.reference_id) if self.reference_id else None,
            "description": self.description,
            "created_at": self.created_at.isoformat()
        }
