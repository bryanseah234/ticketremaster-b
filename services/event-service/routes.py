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
