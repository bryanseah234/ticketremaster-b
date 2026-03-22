import uuid
from datetime import UTC, datetime

from app import db


class TicketLog(db.Model):
    __tablename__ = 'ticket_logs'

    logId = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticketId = db.Column(db.String(36), nullable=False, index=True)
    staffId = db.Column(db.String(36), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'logId': self.logId,
            'ticketId': self.ticketId,
            'staffId': self.staffId,
            'status': self.status,
            'timestamp': self.timestamp.isoformat(),
        }
