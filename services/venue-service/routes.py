from flask import Blueprint, jsonify

from app import db
from models import Venue

bp = Blueprint('venues', __name__)


def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code


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


@bp.get('/venues')
def list_venues():
    """
    List all active venues
    ---
    tags:
      - Venues
    responses:
      200:
        description: List of active venues
        schema:
          type: object
          properties:
            venues:
              type: array
              items:
                $ref: '#/definitions/Venue'
    definitions:
      Venue:
        type: object
        properties:
          venueId:
            type: string
            format: uuid
          name:
            type: string
          isActive:
            type: boolean
          createdAt:
            type: string
            format: date-time
          updatedAt:
            type: string
            format: date-time
    """
    venues = Venue.query.filter_by(isActive=True).order_by(Venue.name.asc()).all()
    return jsonify({'venues': [venue.to_dict() for venue in venues]}), 200


@bp.get('/venues/<venue_id>')
def get_venue(venue_id):
    """
    Get venue by ID
    ---
    tags:
      - Venues
    parameters:
      - in: path
        name: venue_id
        type: string
        required: true
    responses:
      200:
        description: Venue details
        schema:
          $ref: '#/definitions/Venue'
      404:
        description: Venue not found
    """
    venue = db.session.get(Venue, venue_id)
    if not venue:
        return error_response(404, 'VENUE_NOT_FOUND', 'Venue not found')
    return jsonify(venue.to_dict()), 200
