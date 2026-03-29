import uuid
from datetime import UTC, datetime, timedelta

from app import db


class PasswordResetToken(db.Model):
    """Token model for password reset flow with TTL."""
    __tablename__ = 'password_reset_tokens'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    userId = db.Column(db.String(36), db.ForeignKey('users.userId'), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    expiresAt = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    createdAt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    # Relationship to User
    user = db.relationship('User', backref=db.backref('passwordResetTokens', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'userId': self.userId,
            'expiresAt': self.expiresAt.isoformat() if self.expiresAt else None,
            'used': self.used,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None,
        }


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
    favoriteEvents = db.Column(db.ARRAY(db.String), nullable=False, default=list)
    createdAt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def to_dict(self, include_sensitive=False):
        payload = {
            'userId': self.userId,
            'email': self.email,
            'phoneNumber': self.phoneNumber,
            'role': self.role,
            'isFlagged': self.isFlagged,
            'venueId': self.venueId,
            'favoriteEvents': self.favoriteEvents or [],
            'createdAt': self.createdAt.isoformat(),
        }
        if include_sensitive:
            payload['password'] = self.password
            payload['salt'] = self.salt
        return payload
