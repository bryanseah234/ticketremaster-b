from src.extensions import db
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Venue(db.Model):
    __tablename__ = 'venues'

    venue_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.Text, nullable=False)
    total_halls = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            'venue_id': str(self.venue_id),
            'name': self.name,
            'address': self.address,
            'total_halls': self.total_halls
        }
