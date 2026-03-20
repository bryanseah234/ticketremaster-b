from flask import Blueprint, jsonify

from app import db
from models import Venue

bp = Blueprint('venues', __name__)


def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'}), 200


@bp.get('/venues')
def list_venues():
    venues = Venue.query.filter_by(isActive=True).order_by(Venue.name.asc()).all()
    return jsonify({'venues': [venue.to_dict() for venue in venues]}), 200


@bp.get('/venues/<venue_id>')
def get_venue(venue_id):
    venue = db.session.get(Venue, venue_id)
    if not venue:
        return error_response(404, 'VENUE_NOT_FOUND', 'Venue not found')
    return jsonify(venue.to_dict()), 200
