from flask import Blueprint, jsonify, request

from models import SeatInventory
from app import db

bp = Blueprint('seat_inventory', __name__)


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'}), 200


@bp.get('/inventory/event/<event_id>')
def list_inventory_by_event(event_id):
    inventory = (
        SeatInventory.query.filter_by(eventId=event_id)
        .order_by(SeatInventory.seatId.asc())
        .all()
    )
    return jsonify({'eventId': event_id, 'inventory': [item.to_dict(include_internal=False) for item in inventory]}), 200


@bp.post('/inventory/batch')
def create_inventory_batch():
    """
    Create multiple seat inventory records for an event (admin)
    """
    data = request.get_json(silent=True) or {}
    event_id = data.get('eventId')
    seats = data.get('seats', [])

    if not all([event_id, seats]):
        return jsonify({'error': {'code': 'VALIDATION_ERROR', 'message': 'Missing required fields: eventId, seats'}}), 400

    if not isinstance(seats, list):
        return jsonify({'error': {'code': 'VALIDATION_ERROR', 'message': 'seats must be a non-empty list'}}), 400

    normalized_seats = []
    for seat in seats:
        if not isinstance(seat, dict):
            return jsonify({'error': {'code': 'VALIDATION_ERROR', 'message': 'Each seat entry must be an object'}}), 400
        seat_id = seat.get('seatId')
        if not seat_id:
            return jsonify({'error': {'code': 'VALIDATION_ERROR', 'message': 'Each seat entry must include seatId'}}), 400
        status = seat.get('status', 'available')
        if not isinstance(status, str) or not status:
            return jsonify({'error': {'code': 'VALIDATION_ERROR', 'message': 'Seat status must be a non-empty string'}}), 400
        normalized_seats.append({'seatId': seat_id, 'status': status})

    # Check if inventory already exists for this event
    existing = SeatInventory.query.filter_by(eventId=event_id).first()
    if existing:
        return jsonify({'error': {'code': 'ALREADY_EXISTS', 'message': 'Inventory already exists for this event'}}), 409

    try:
        to_create = []
        for seat in normalized_seats:
            inv = SeatInventory(
                eventId=event_id,
                seatId=seat['seatId'],
                status=seat['status'],
            )
            to_create.append(inv)

        db.session.bulk_save_objects(to_create)
        db.session.commit()

        return jsonify({
            'data': {
                'eventId': event_id,
                'createdCount': len(to_create),
            }
        }), 201
    except Exception:
        db.session.rollback()
        return jsonify({'error': {'code': 'DB_ERROR', 'message': 'Could not create inventory records'}}), 500
