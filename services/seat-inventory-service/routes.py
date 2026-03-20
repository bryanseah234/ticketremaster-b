from flask import Blueprint, jsonify

from models import SeatInventory

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
