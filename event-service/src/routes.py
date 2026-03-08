from flask import Blueprint, jsonify, request
from src.services.event_service import get_all_events, get_event_by_id, create_event
from src.extensions import db
from sqlalchemy import text

event_bp = Blueprint('events', __name__)

@event_bp.route('/events', methods=['GET'])
def list_events():
    """
    List all upcoming events
    ---
    tags:
      - Events
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 20
    responses:
      200:
        description: List of events
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    result = get_all_events(page, per_page)
    return jsonify({
        "success": True,
        "data": result['data'],
        "pagination": result['pagination']
    }), 200

@event_bp.route('/events/<uuid:event_id>', methods=['GET'])
def get_event(event_id):
    """
    Get a single event with seat map
    ---
    tags:
      - Events
    parameters:
      - name: event_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Event details
      404:
        description: Event not found
      400:
        description: Invalid UUID
    """
    event = get_event_by_id(event_id)
    if not event:
        return jsonify({
            "success": False,
            "error_code": "EVENT_NOT_FOUND",
            "message": "The requested event could not be found."
        }), 404
        
    return jsonify({
        "success": True,
        "data": event
    }), 200

@event_bp.route('/events', methods=['POST'])
def add_event():
    """
    Create a new event
    """
    data = request.get_json()
    if not data or not data.get('name') or not data.get('venue') or not data.get('hall_id') or not data.get('event_date') or not data.get('total_seats') or not data.get('pricing_tiers'):
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "Missing required fields"}), 400
    
    try:
        event_dict = create_event(data)
        return jsonify({"success": True, "data": event_dict}), 201
    except Exception as e:
        return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": str(e)}), 500
