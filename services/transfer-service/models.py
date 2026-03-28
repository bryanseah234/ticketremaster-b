import uuid
from datetime import UTC, datetime

from app import db


class Transfer(db.Model):
    __tablename__ = 'transfers'

    transferId = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    listingId = db.Column(db.String(36), nullable=False, index=True)
    buyerId = db.Column(db.String(36), nullable=False)
    sellerId = db.Column(db.String(36), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='pending_seller_acceptance')
    creditAmount = db.Column(db.Float, nullable=False)
    buyerOtpVerified = db.Column(db.Boolean, nullable=False, default=False)
    sellerOtpVerified = db.Column(db.Boolean, nullable=False, default=False)
    buyerVerificationSid = db.Column(db.String(64), nullable=True)
    sellerVerificationSid = db.Column(db.String(64), nullable=True)
    completedAt = db.Column(db.DateTime, nullable=True)
    createdAt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'transferId': self.transferId,
            'listingId': self.listingId,
            'buyerId': self.buyerId,
            'sellerId': self.sellerId,
            'status': self.status,
            'creditAmount': self.creditAmount,
            'buyerOtpVerified': self.buyerOtpVerified,
            'sellerOtpVerified': self.sellerOtpVerified,
            'buyerVerificationSid': self.buyerVerificationSid,
            'sellerVerificationSid': self.sellerVerificationSid,
            'completedAt': self.completedAt.isoformat() if self.completedAt else None,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None,
        }
