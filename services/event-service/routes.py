from datetime import datetime
from typing import Optional, Tuple

from flask import Blueprint, jsonify, request

from app import db
from models import Event

bp = Blueprint('events', __name__)

# Valid event types
VALID_EVENT_TYPES = {'concert', 'sports', 'theater', 'conference', 'festival', 'other'}


def error_response(status_code: int, code: str, message: str) -> Tuple[dict, int]:
    return jsonify({'error': {'code': code, 'message': message}}), status_code


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string to datetime object."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


REQUIRED_FIELDS = ('venueId', 'name', 'date', 'type', 'price')
UPDATABLE_FIELDS = {'venueId', 'name', 'date', 'description', 'type', 'image', 'price'}


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


@bp.get('/events')
def list_events():
    """
    List all events
    ---
    tags:
      - Events
    parameters:
      - in: query
        name: page
        type: integer
        default: 1
      - in: query
        name: limit
        type: integer
        default: 20
      - in: query
        name: type
        type: string
        description: Filter by event type (concert, sports, theater, conference, festival, other)
    responses:
      200:
        description: Paginated list of events
        schema:
          type: object
          properties:
            events:
              type: array
              items:
                $ref: '#/definitions/Event'
            pagination:
              $ref: '#/definitions/Pagination'
    """
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


@bp.post('/admin/events/<event_id>/publish')
def publish_event(event_id: str):
    """
    Publish an event (admin)
    ---
    tags:
      - Admin Events
    parameters:
      - in: path
        name: event_id
        type: string
        required: true
    responses:
      200:
        description: Event published
        schema:
          type: object
          properties:
            message:
              type: string
            event:
              $ref: '#/definitions/Event'
      400:
        description: Event already cancelled or in the past
      404:
        description: Event not found
    """
    event = db.session.get(Event, event_id)
    if not event:
        return error_response(404, 'EVENT_NOT_FOUND', 'Event not found')

    if event.cancelledAt is not None:
        return error_response(400, 'EVENT_CANCELLED', 'Cannot publish a cancelled event')

    # Check if event date is in the past
    if event.date < datetime.now(datetime.timezone.utc):
        return error_response(400, 'EVENT_IN_PAST', 'Cannot publish an event that has already passed')

    # Mark as published (using updatedAt as a simple publish indicator)
    event.updatedAt = datetime.now(datetime.timezone.utc)
    db.session.commit()

    return jsonify({
        'message': 'Event published successfully',
        'event': event.to_dict()
    }), 200


@bp.post('/admin/events/<event_id>/duplicate')
def duplicate_event(event_id: str):
    """
    Duplicate an event (admin)
    ---
    tags:
      - Admin Events
    parameters:
      - in: path
        name: event_id
        type: string
        required: true
      - in: body
        name: body
        schema:
          type: object
          properties:
            name:
              type: string
              description: Name for the duplicated event (defaults to original name + " (Copy)")
    responses:
      201:
        description: Event duplicated
        schema:
          type: object
          properties:
            message:
              type: string
            event:
              $ref: '#/definitions/Event'
      404:
        description: Event not found
    """
    event = db.session.get(Event, event_id)
    if not event:
        return error_response(404, 'EVENT_NOT_FOUND', 'Event not found')

    data = request.get_json(silent=True) or {}
    new_name = data.get('name', f"{event.name} (Copy)")

    new_event = Event(
        venueId=event.venueId,
        name=new_name,
        date=event.date,
        description=event.description,
        type=event.type,
        image=event.image,
        price=event.price,
    )
    db.session.add(new_event)
    db.session.commit()

    return jsonify({
        'message': 'Event duplicated successfully',
        'event': new_event.to_dict()
    }), 201


@bp.get('/events/upcoming')
def list_upcoming_events():
    """
    List upcoming events
    ---
    tags:
      - Events
    parameters:
      - in: query
        name: page
        type: integer
        default: 1
      - in: query
        name: limit
        type: integer
        default: 20
      - in: query
        name: type
        type: string
    responses:
      200:
        description: Paginated list of upcoming events
        schema:
          type: object
          properties:
            events:
              type: array
              items:
                $ref: '#/definitions/Event'
            pagination:
              $ref: '#/definitions/Pagination'
    """
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=20, type=int)
    event_type = request.args.get('type', type=str)

    if page < 1:
        return error_response(400, 'VALIDATION_ERROR', 'page must be >= 1')
    if limit < 1 or limit > 100:
        return error_response(400, 'VALIDATION_ERROR', 'limit must be between 1 and 100')

    now = datetime.now(datetime.timezone.utc)
    query = Event.query.filter(
        Event.cancelledAt.is_(None),
        Event.date >= now
    )

    if event_type:
        query = query.filter(Event.type.ilike(event_type.strip()))

    total = query.count()
    events = (
        query.order_by(Event.date.asc())
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


@bp.get('/events/search')
def search_events():
    """
    Search events by name or description
    ---
    tags:
      - Events
    parameters:
      - in: query
        name: q
        type: string
        required: true
        description: Search query string
      - in: query
        name: page
        type: integer
        default: 1
      - in: query
        name: limit
        type: integer
        default: 20
    responses:
      200:
        description: Matching events
        schema:
          type: object
          properties:
            events:
              type: array
              items:
                $ref: '#/definitions/Event'
            pagination:
              $ref: '#/definitions/Pagination'
      400:
        description: Missing search query
    """
    query_param = request.args.get('q', default='', type=str)
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=20, type=int)

    if not query_param:
        return error_response(400, 'VALIDATION_ERROR', 'Search query "q" is required')

    if page < 1:
        return error_response(400, 'VALIDATION_ERROR', 'page must be >= 1')
    if limit < 1 or limit > 100:
        return error_response(400, 'VALIDATION_ERROR', 'limit must be between 1 and 100')

    search_term = f"%{query_param.strip()}%"
    query = Event.query.filter(
        Event.cancelledAt.is_(None),
        (Event.name.ilike(search_term)) | (Event.description.ilike(search_term))
    )

    total = query.count()
    events = (
        query.order_by(Event.date.asc())
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


@bp.get('/events/types')
def list_event_types():
    """
    Get available event types
    ---
    tags:
      - Events
    responses:
      200:
        description: List of event types
        schema:
          type: object
          properties:
            types:
              type: array
              items:
                type: object
                properties:
                  value:
                    type: string
                  label:
                    type: string
    """
    types = [
        {'value': 'concert', 'label': 'Concert'},
        {'value': 'sports', 'label': 'Sports'},
        {'value': 'theater', 'label': 'Theater'},
        {'value': 'conference', 'label': 'Conference'},
        {'value': 'festival', 'label': 'Festival'},
        {'value': 'other', 'label': 'Other'},
    ]
    return jsonify({'types': types}), 200


@bp.get('/events/<event_id>')
def get_event(event_id):
    """
    Get event by ID
    ---
    tags:
      - Events
    parameters:
      - in: path
        name: event_id
        type: string
        required: true
    responses:
      200:
        description: Event details
        schema:
          $ref: '#/definitions/Event'
      404:
        description: Event not found
    """
    event = db.session.get(Event, event_id)
    if not event:
        return error_response(404, 'EVENT_NOT_FOUND', 'Event not found')
    return jsonify(event.to_dict()), 200


@bp.post('/events')
def create_event():
    """
    Create an event
    ---
    tags:
      - Events
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [venueId, name, date, type, price]
          properties:
            venueId:
              type: string
              format: uuid
            name:
              type: string
            date:
              type: string
              format: date-time
            type:
              type: string
              enum: [concert, sports, theater, conference, festival, other]
            price:
              type: number
            description:
              type: string
            image:
              type: string
    responses:
      201:
        description: Event created
        schema:
          type: object
          properties:
            eventId:
              type: string
              format: uuid
            venueId:
              type: string
              format: uuid
            name:
              type: string
            createdAt:
              type: string
              format: date-time
      400:
        description: Missing required fields or invalid date
    definitions:
      Event:
        type: object
        properties:
          eventId:
            type: string
            format: uuid
          venueId:
            type: string
            format: uuid
          name:
            type: string
          date:
            type: string
            format: date-time
          type:
            type: string
          price:
            type: number
          description:
            type: string
          image:
            type: string
          cancelledAt:
            type: string
            format: date-time
          createdAt:
            type: string
            format: date-time
          updatedAt:
            type: string
            format: date-time
      Pagination:
        type: object
        properties:
          page:
            type: integer
          limit:
            type: integer
          total:
            type: integer
    """
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
    """
    Update event (admin)
    ---
    tags:
      - Admin Events
    parameters:
      - in: path
        name: event_id
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            venueId:
              type: string
              format: uuid
            name:
              type: string
            date:
              type: string
              format: date-time
            type:
              type: string
            description:
              type: string
            image:
              type: string
            price:
              type: number
    responses:
      200:
        description: Updated event
        schema:
          $ref: '#/definitions/Event'
      400:
        description: Validation error or event already cancelled
      404:
        description: Event not found
    """
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
    """
    Cancel event (admin, soft delete)
    ---
    tags:
      - Admin Events
    parameters:
      - in: path
        name: event_id
        type: string
        required: true
    responses:
      200:
        description: Event cancelled
        schema:
          type: object
          properties:
            message:
              type: string
            event:
              $ref: '#/definitions/Event'
      400:
        description: Event already cancelled
      404:
        description: Event not found
    """
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
    """
    Cancel event with optional reason (admin)
    ---
    tags:
      - Admin Events
    parameters:
      - in: path
        name: event_id
        type: string
        required: true
      - in: body
        name: body
        schema:
          type: object
          properties:
            reason:
              type: string
    responses:
      200:
        description: Event cancelled
        schema:
          type: object
          properties:
            message:
              type: string
            event:
              $ref: '#/definitions/Event'
            cancelReason:
              type: string
      400:
        description: Event already cancelled
      404:
        description: Event not found
    """
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
    """
    List all events including cancelled (admin)
    ---
    tags:
      - Admin Events
    parameters:
      - in: query
        name: page
        type: integer
        default: 1
      - in: query
        name: limit
        type: integer
        default: 20
      - in: query
        name: include_cancelled
        type: string
        enum: ['true', 'false']
        default: 'false'
    responses:
      200:
        description: Paginated list of events
        schema:
          type: object
          properties:
            events:
              type: array
              items:
                $ref: '#/definitions/Event'
            pagination:
              $ref: '#/definitions/Pagination'
    """
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
