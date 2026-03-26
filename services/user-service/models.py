import uuid
from datetime import UTC, datetime

from app import db

class User(db.Model):
    __tablename__ = 'users'

    userId = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    salt = db.Column(db.String(255), nullable=False)
    phoneNumber = db.Column(db.String(20), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    isFlagged = db.Column(db.Boolean, nullable=False, default=False)
    venueId = db.Column(db.String(36), nullable=True)
    createdAt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def to_dict(self, include_sensitive=False):
        payload = {
            'userId': self.userId,
            'email': self.email,
            'phoneNumber': self.phoneNumber,
            'role': self.role,
            'isFlagged': self.isFlagged,
            'venueId': self.venueId,
            'createdAt': self.createdAt.isoformat(),
        }
        if include_sensitive:
            payload['password'] = self.password
            payload['salt'] = self.salt
        return payload