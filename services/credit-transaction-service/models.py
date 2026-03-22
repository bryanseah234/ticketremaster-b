import uuid
from datetime import UTC, datetime

from app import db


class CreditTransaction(db.Model):
    __tablename__ = 'credit_txns'

    txnId = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    userId = db.Column(db.String(36), nullable=False, index=True)
    delta = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    referenceId = db.Column(db.String(100), nullable=True, index=True)
    createdAt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'txnId': self.txnId,
            'userId': self.userId,
            'delta': self.delta,
            'reason': self.reason,
            'referenceId': self.referenceId,
            'createdAt': self.createdAt.isoformat(),
        }
