"""
Entry Log Model — Inventory Service
Results: SUCCESS | DUPLICATE | WRONG_HALL | UNPAID | NOT_FOUND | EXPIRED
"""

import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from src.db import Base


class EntryLog(Base):
    __tablename__ = "entry_logs"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seat_id = Column(UUID(as_uuid=True), ForeignKey("seats.seat_id"), nullable=False)
    scanned_at = Column(DateTime, server_default="now()")
    scanned_by_staff_id = Column(UUID(as_uuid=True), nullable=True)
    result = Column(
        SAEnum("SUCCESS", "DUPLICATE", "WRONG_HALL", "UNPAID", "NOT_FOUND", "EXPIRED",
               name="entry_result", create_type=False),
        nullable=False,
    )
    hall_id_presented = Column(String(20), nullable=True)
    hall_id_expected = Column(String(20), nullable=True)
