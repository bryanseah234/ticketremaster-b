"""
Seat Model — Inventory Service
States: AVAILABLE | HELD | SOLD | CHECKED_IN
"""

import uuid
from sqlalchemy import Column, String, Integer, Numeric, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from src.db import Base


class Seat(Base):
    __tablename__ = "seats"

    seat_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), nullable=False)
    owner_user_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(
        SAEnum("AVAILABLE", "HELD", "SOLD", "CHECKED_IN", name="seat_status", create_type=False),
        nullable=False,
        default="AVAILABLE",
    )
    held_by_user_id = Column(UUID(as_uuid=True), nullable=True)
    held_until = Column(DateTime, nullable=True)
    qr_code_hash = Column(String, nullable=True)
    price_paid = Column(Numeric(10, 2), nullable=True)
    row_number = Column(String(4), nullable=False)
    seat_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default="now()")
    updated_at = Column(DateTime, server_default="now()")

    def to_dict(self):
        return {
            "seat_id": str(self.seat_id),
            "event_id": str(self.event_id),
            "owner_user_id": str(self.owner_user_id) if self.owner_user_id else None,
            "status": self.status,
            "held_by_user_id": str(self.held_by_user_id) if self.held_by_user_id else None,
            "held_until": self.held_until.isoformat() if self.held_until else None,
            "row_number": self.row_number,
            "seat_number": self.seat_number,
            "price_paid": float(self.price_paid) if self.price_paid else None,
        }
