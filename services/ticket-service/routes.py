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
    """
    Health check
    ---
    tags:
      - Health
    responses:
      200:
        description: Service is healthy
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
    """
    return jsonify({'status': 'ok'}), 200


@bp.post('/tickets')
def create_ticket():
    """
    Create a ticket
    ---
    tags:
      - Tickets
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [inventoryId, ownerId, venueId, eventId, price]
          properties:
            inventoryId:
              type: string
              format: uuid
            ownerId:
              type: string
              format: uuid
            venueId:
              type: string
              format: uuid
            eventId:
              type: string
              format: uuid
            price:
              type: number
            status:
              type: string
              enum: [active, listed, used, pending_transfer]
              default: active
            qrHash:
              type: string
              description: Pre-generated QR hash (auto-generated if omitted)
            qrTimestamp:
              type: string
              format: date-time
    responses:
      201:
        description: Ticket created
        schema:
          $ref: '#/definitions/Ticket'
      400:
        description: Missing required fields or invalid status
    definitions:
      Ticket:
        type: object
        properties:
          ticketId:
            type: string
            format: uuid
          inventoryId:
            type: string
            format: uuid
          ownerId:
            type: string
            format: uuid
          venueId:
            type: string
            format: uuid
          eventId:
            type: string
            format: uuid
          price:
            type: number
          status:
            type: string
            enum: [active, listed, used, pending_transfer]
          qrHash:
            type: string
          qrTimestamp:
            type: string
            format: date-time
          createdAt:
            type: string
            format: date-time
          updatedAt:
            type: string
            format: date-time
    """
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
    """
    Get ticket by ID
    ---
    tags:
      - Tickets
    parameters:
      - in: path
        name: ticket_id
        type: string
        required: true
    responses:
      200:
        description: Ticket details
        schema:
          $ref: '#/definitions/Ticket'
      404:
        description: Ticket not found
    """
    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        return error_response(404, 'TICKET_NOT_FOUND', 'Ticket not found')
    return jsonify(ticket.to_dict()), 200


@bp.get('/tickets/owner/<owner_id>')
def get_tickets_by_owner(owner_id):
    """
    List tickets by owner
    ---
    tags:
      - Tickets
    parameters:
      - in: path
        name: owner_id
        type: string
        required: true
    responses:
      200:
        description: Tickets owned by the user
        schema:
          type: object
          properties:
            tickets:
              type: array
              items:
                $ref: '#/definitions/Ticket'
    """
    tickets = Ticket.query.filter_by(ownerId=owner_id).order_by(Ticket.createdAt.desc()).all()
    return jsonify({'tickets': [ticket.to_dict() for ticket in tickets]}), 200


@bp.get('/tickets/event/<event_id>')
def get_tickets_by_event(event_id):
    """
    List tickets for an event
    ---
    tags:
      - Tickets
    parameters:
      - in: path
        name: event_id
        type: string
        required: true
    responses:
      200:
        description: Tickets for the event
        schema:
          type: object
          properties:
            tickets:
              type: array
              items:
                $ref: '#/definitions/Ticket'
    """
    tickets = Ticket.query.filter_by(eventId=event_id).order_by(Ticket.createdAt.desc()).all()
    return jsonify({'tickets': [ticket.to_dict() for ticket in tickets]}), 200


@bp.get('/tickets/qr/<qr_hash>')
def get_ticket_by_qr_hash(qr_hash):
    """
    Get ticket by QR code hash
    ---
    tags:
      - Tickets
    parameters:
      - in: path
        name: qr_hash
        type: string
        required: true
    responses:
      200:
        description: Ticket matching the QR hash
        schema:
          $ref: '#/definitions/Ticket'
      404:
        description: Ticket not found
    """
    ticket = Ticket.query.filter_by(qrHash=qr_hash).first()
    if not ticket:
        return error_response(404, 'TICKET_NOT_FOUND', 'Ticket not found')
    return jsonify(ticket.to_dict()), 200


@bp.patch('/tickets/<ticket_id>')
def update_ticket(ticket_id):
    """
    Update ticket
    ---
    tags:
      - Tickets
    parameters:
      - in: path
        name: ticket_id
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            status:
              type: string
              enum: [active, listed, used, pending_transfer]
            ownerId:
              type: string
              format: uuid
            qrHash:
              type: string
            qrTimestamp:
              type: string
              format: date-time
    responses:
      200:
        description: Updated ticket
        schema:
          $ref: '#/definitions/Ticket'
      400:
        description: Validation error or invalid datetime
      404:
        description: Ticket not found
      409:
        description: Duplicate QR hash
    """
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
