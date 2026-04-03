import uuid
from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from models import Ticket

bp = Blueprint('tickets', __name__)


REQUIRED_FIELDS = ('inventoryId', 'ownerId', 'venueId', 'eventId', 'price')
UPDATABLE_FIELDS = {'status', 'ownerId', 'qrHash', 'qrTimestamp'}
ALLOWED_STATUS_VALUES = {'active', 'listed', 'used', 'pending_transfer'}


def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code


def parse_datetime(value):
    if value is None:
        return None
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'}), 200


@bp.post('/tickets')
def create_ticket():
    data = request.get_json(silent=True)
    if not data or any(field not in data for field in REQUIRED_FIELDS):
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields')

    ticket = Ticket(
        inventoryId=data['inventoryId'],
        ownerId=data['ownerId'],
        venueId=data['venueId'],
        eventId=data['eventId'],
        price=data['price'],
        status=data.get('status', 'active'),
        qrHash=uuid.uuid4().hex,
        qrTimestamp=datetime.now(UTC),
    )

    if ticket.status not in ALLOWED_STATUS_VALUES:
        return error_response(400, 'VALIDATION_ERROR', 'Invalid status value')

    db.session.add(ticket)
    db.session.commit()
    return jsonify(ticket.to_dict()), 201


@bp.get('/tickets/<ticket_id>')
def get_ticket(ticket_id):
    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        return error_response(404, 'TICKET_NOT_FOUND', 'Ticket not found')
    return jsonify(ticket.to_dict()), 200


@bp.get('/tickets/owner/<owner_id>')
def get_tickets_by_owner(owner_id):
    tickets = Ticket.query.filter_by(ownerId=owner_id).order_by(Ticket.createdAt.desc()).all()
    return jsonify({'tickets': [ticket.to_dict() for ticket in tickets]}), 200


@bp.get('/tickets/event/<event_id>')
def get_tickets_by_event(event_id):
    tickets = Ticket.query.filter_by(eventId=event_id).order_by(Ticket.createdAt.desc()).all()
    return jsonify({'tickets': [ticket.to_dict() for ticket in tickets]}), 200


@bp.get('/tickets/qr/<qr_hash>')
def get_ticket_by_qr_hash(qr_hash):
    ticket = Ticket.query.filter_by(qrHash=qr_hash).first()
    if not ticket:
        return error_response(404, 'TICKET_NOT_FOUND', 'Ticket not found')
    return jsonify(ticket.to_dict()), 200


@bp.patch('/tickets/<ticket_id>')
def update_ticket(ticket_id):
    data = request.get_json(silent=True)
    if not data:
        return error_response(400, 'VALIDATION_ERROR', 'Request body is required')

    invalid_fields = set(data.keys()) - UPDATABLE_FIELDS
    if invalid_fields:
        return error_response(400, 'VALIDATION_ERROR', 'Request contains unsupported fields')

    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        return error_response(404, 'TICKET_NOT_FOUND', 'Ticket not found')

    if 'status' in data and data['status'] not in ALLOWED_STATUS_VALUES:
        return error_response(400, 'VALIDATION_ERROR', 'Invalid status value')

    for field, value in data.items():
        if field == 'qrTimestamp' and value is not None:
            try:
                value = parse_datetime(value)
            except (ValueError, TypeError):
                return error_response(400, 'INVALID_DATETIME', 'Invalid datetime format')
        setattr(ticket, field, value)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response(409, 'DUPLICATE_QR_HASH', 'QR hash already exists')

    return jsonify(ticket.to_dict()), 200
