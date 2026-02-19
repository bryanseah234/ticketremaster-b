import uuid
import bcrypt
from sqlalchemy.dialects.postgresql import UUID
from src.extensions import db

class User(db.Model):
    __tablename__ = 'users'

    user_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.Text, nullable=False)
    credit_balance = db.Column(db.Numeric(10, 2), default=0.00)
    # two_fa_secret column exists in DB but maybe we don't need it in model yet if not implementing 2FA immediately
    # But good to include.
    two_fa_secret = db.Column(db.Text)
    is_flagged = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def to_dict(self):
        return {
            'user_id': str(self.user_id),
            'email': self.email,
            'phone': self.phone,
            'credit_balance': float(self.credit_balance) if self.credit_balance else 0.0,
            'is_flagged': self.is_flagged
        }
