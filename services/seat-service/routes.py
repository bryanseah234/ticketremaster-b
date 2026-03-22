from flask import Blueprint, jsonify

from models import Seat

bp = Blueprint('seats', __name__)


@bp.get('/health')
def health_check():
    return jsonify({'status': 'ok'}), 200


@bp.get('/seats/venue/<venue_id>')
def list_seats_for_venue(venue_id):
    seats = (
        Seat.query.filter_by(venueId=venue_id)
        .order_by(Seat.rowNumber.asc(), Seat.seatNumber.asc())
        .all()
    )
    return jsonify({'seats': [seat.to_dict() for seat in seats]}), 200
