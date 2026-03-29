from datetime import datetime

from flask import Blueprint, jsonify, request

from app import db
from models import Event

bp = Blueprint('events', __name__)


def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code


def parse_datetime(value):
    """Parse ISO datetime string to datetime object."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


REQUIRED_FIELDS = ('venueId', 'name', 'date', 'type', 'price')
UPDATABLE_FIELDS = {'venueId', 'name', 'date', 'description', 'type', 'image', 'price'}


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'}), 200


@bp.get('/events')
def list_events():
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=20, type=int)
    event_type = request.args.get('type', type=str)

    if page is None or page < 1:
        return error_response(400, 'VALIDATION_ERROR', 'page must be an integer greater than or equal to 1')
    if limit is None or limit < 1:
        return error_response(400, 'VALIDATION_ERROR', 'limit must be an integer greater than or equal to 1')

    limit = min(limit, 100)

    query = Event.query
    if event_type:
        query = query.filter(Event.type.ilike(event_type.strip()))

    total = query.count()
    events = (
        query.order_by(Event.date.asc(), Event.createdAt.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return jsonify({
        'events': [e.to_dict(summary=True) for e in events],
        'pagination': {
            'page': page,
            'limit': limit,
            'total': total,
        },
    }), 200


@bp.get('/events/<event_id>')
def get_event(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        return error_response(404, 'EVENT_NOT_FOUND', 'Event not found')
    return jsonify(event.to_dict()), 200


@bp.post('/events')
def create_event():
    data = request.get_json(silent=True)
    if not data or any(field not in data for field in REQUIRED_FIELDS):
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields')

    try:
        event_date = parse_datetime(data['date'])
    except (ValueError, TypeError):
        return error_response(400, 'INVALID_DATE', 'Invalid date format')

    event = Event(
        venueId=data['venueId'],
        name=data['name'],
        date=event_date,
        description=data.get('description'),
        type=data['type'],
        image=data.get('image'),
        price=data['price'],
    )
    db.session.add(event)
    db.session.commit()

    return jsonify({
        'eventId': event.eventId,
        'venueId': event.venueId,
        'name': event.name,
        'createdAt': event.createdAt.isoformat(),
    }), 201


@bp.put('/admin/events/<event_id>')
def update_event(event_id):
    """Admin endpoint to update event details."""
    data = request.get_json(silent=True)
    if not data:
        return error_response(400, 'VALIDATION_ERROR', 'Request body is required')

    # Check for invalid fields
    invalid_fields = set(data.keys()) - UPDATABLE_FIELDS
    if invalid_fields:
        return error_response(400, 'VALIDATION_ERROR', f'Request contains unsupported fields: {invalid_fields}')

    event = db.session.get(Event, event_id)
    if not event:
        return error_response(404, 'EVENT_NOT_FOUND', 'Event not found')

    # Check if event is already cancelled
    if event.cancelledAt is not None:
        return error_response(400, 'EVENT_CANCELLED', 'Cannot update a cancelled event')

    # Parse and validate date if provided
    if 'date' in data:
        try:
            data['date'] = parse_datetime(data['date'])
        except (ValueError, TypeError):
            return error_response(400, 'INVALID_DATE', 'Invalid date format')

    # Update fields
    for field, value in data.items():
        setattr(event, field, value)

    db.session.commit()
    return jsonify(event.to_dict()), 200


@bp.delete('/admin/events/<event_id>')
def delete_event(event_id):
    """Admin endpoint to soft-delete (cancel) an event."""
    event = db.session.get(Event, event_id)
    if not event:
        return error_response(404, 'EVENT_NOT_FOUND', 'Event not found')

    # Check if already cancelled
    if event.cancelledAt is not None:
        return error_response(400, 'EVENT_ALREADY_CANCELLED', 'Event is already cancelled')

    event.cancelledAt = datetime.now(datetime.timezone.utc)
    db.session.commit()

    return jsonify({
        'message': 'Event cancelled successfully',
        'event': event.to_dict()
    }), 200


@bp.post('/admin/events/<event_id>/cancel')
def cancel_event(event_id):
    """Admin endpoint to cancel an event with optional reason."""
    event = db.session.get(Event, event_id)
    if not event:
        return error_response(404, 'EVENT_NOT_FOUND', 'Event not found')

    # Check if already cancelled
    if event.cancelledAt is not None:
        return error_response(400, 'EVENT_ALREADY_CANCELLED', 'Event is already cancelled')

    data = request.get_json(silent=True) or {}
    cancel_reason = data.get('reason')

    event.cancelledAt = datetime.now(datetime.timezone.utc)
    db.session.commit()

    response = {
        'message': 'Event cancelled successfully',
        'event': event.to_dict()
    }
    if cancel_reason:
        response['cancelReason'] = cancel_reason

    return jsonify(response), 200


@bp.get('/admin/events')
def admin_list_events():
    """Admin endpoint to list all events including cancelled ones."""
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=20, type=int)
    include_cancelled = request.args.get('include_cancelled', default='false', type=str)

    if page is None or page < 1:
        return error_response(400, 'VALIDATION_ERROR', 'page must be an integer greater than or equal to 1')
    if limit is None or limit < 1:
        return error_response(400, 'VALIDATION_ERROR', 'limit must be an integer greater than or equal to 1')

    limit = min(limit, 100)

    query = Event.query
    if include_cancelled != 'true':
        query = query.filter(Event.cancelledAt.is_(None))

    total = query.count()
    events = (
        query.order_by(Event.date.asc(), Event.createdAt.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return jsonify({
        'events': [e.to_dict(summary=True) for e in events],
        'pagination': {
            'page': page,
            'limit': limit,
            'total': total,
        },
    }), 200
