from flask import Blueprint, jsonify, request

from app import db
from models import Listing

bp = Blueprint('listings', __name__)


REQUIRED_FIELDS = ('ticketId', 'sellerId', 'price')
UPDATABLE_FIELDS = {'status'}
ALLOWED_STATUSES = {'active', 'completed', 'cancelled'}


def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'}), 200


@bp.post('/listings')
def create_listing():
    data = request.get_json(silent=True)
    if not data or any(field not in data for field in REQUIRED_FIELDS):
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields')

    status = data.get('status', 'active')
    if status not in ALLOWED_STATUSES:
        return error_response(400, 'VALIDATION_ERROR', 'Invalid status value')

    listing = Listing(
        ticketId=data['ticketId'],
        sellerId=data['sellerId'],
        price=data['price'],
        status=status,
    )
    db.session.add(listing)
    db.session.commit()
    return jsonify(listing.to_dict()), 201


@bp.get('/listings')
def list_active_listings():
    listings = (
        Listing.query
        .filter_by(status='active')
        .order_by(Listing.createdAt.desc())
        .all()
    )
    return jsonify({'listings': [listing.to_dict() for listing in listings]}), 200


@bp.get('/listings/<listing_id>')
def get_listing(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing:
        return error_response(404, 'LISTING_NOT_FOUND', 'Listing not found')
    return jsonify(listing.to_dict()), 200


@bp.patch('/listings/<listing_id>')
def update_listing(listing_id):
    data = request.get_json(silent=True)
    if not data:
        return error_response(400, 'VALIDATION_ERROR', 'Request body is required')

    invalid_fields = set(data.keys()) - UPDATABLE_FIELDS
    if invalid_fields:
        return error_response(400, 'VALIDATION_ERROR', 'Request contains unsupported fields')

    listing = db.session.get(Listing, listing_id)
    if not listing:
        return error_response(404, 'LISTING_NOT_FOUND', 'Listing not found')

    if data['status'] not in ALLOWED_STATUSES:
        return error_response(400, 'VALIDATION_ERROR', 'Invalid status value')

    listing.status = data['status']
    db.session.commit()

    return jsonify(listing.to_dict()), 200
