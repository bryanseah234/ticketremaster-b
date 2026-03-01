"""
Order Service — Order Service
Handles order CRUD: create, update status, query by seat.
"""

from datetime import datetime, timezone
from db import db
from models.order import Order

def create_order(user_id, seat_id, event_id, credits_charged, status="PENDING"):
    """
    Called by orchestrator when purchase flow starts
    Orchestrator will pass status='CONFIRMED' once credits are deducted and seat is locked
    """
    order = Order(
        user_id=user_id,
        seat_id=seat_id,
        event_id=event_id,
        credits_charged=credits_charged,
        status=status,
        confirmed_at=datetime.now(timezone.utc) if status == "CONFIRMED" else None,
    )
    db.session.add(order)
    db.session.commit()
    return order

def get_order_by_id(order_id):
    return Order.query.filter_by(order_id=order_id).first()

def get_order_by_seat(seat_id):
    """
    Used by orchestrator to confirm a confirmed order exists for scanned seat
    """
    return Order.query.filter_by(seat_id=seat_id).first()

def get_orders_by_user(user_id):
    return Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()

VALID_TRANSITIONS = {
    "PENDING": {"CONFIRMED", "FAILED"},
    "CONFIRMED": {"REFUNDED"},
    "FAILED": set(),
    "REFUNDED": set(),
}

def update_order_status(order_id, new_status):
    """
    Updates order status and enforces valid transitions
    Called by orchestrator:
        - PENDING -> CONFIRMED: after credits deducted + seat confirmed
        - PENDING -> FAILED: after TTL expiry via RabbitMQ DLX
        - CONFIRMED -> REFUNDED: if needed
    """
    order = get_order_by_id(order_id)
    if not order:
        return None, "Order not found"
    
    allowed = VALID_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        return None, f"Cannot transition from {order.status} to {new_status}"
    
    order.status = new_status
    if new_status == "CONFIRMED":
        order.confirmed_at = datetime.now(timezone.utc)
    
    db.session.commit()
    return order, None