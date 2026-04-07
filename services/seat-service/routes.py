from flask import Blueprint, jsonify

from models import Seat

bp = Blueprint('seats', __name__)


@bp.get('/health')
def health_check():
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


@bp.get('/seats/venue/<venue_id>')
def list_seats_for_venue(venue_id):
    """
    List all seats for a venue
    ---
    tags:
      - Seats
    parameters:
      - in: path
        name: venue_id
        type: string
        required: true
    responses:
      200:
        description: Seats ordered by row and seat number
        schema:
          type: object
          properties:
            seats:
              type: array
              items:
                $ref: '#/definitions/Seat'
    definitions:
      Seat:
        type: object
        properties:
          seatId:
            type: string
            format: uuid
          venueId:
            type: string
            format: uuid
          rowNumber:
            type: integer
          seatNumber:
            type: integer
    """
    seats = (
        Seat.query.filter_by(venueId=venue_id)
        .order_by(Seat.rowNumber.asc(), Seat.seatNumber.asc())
        .all()
    )
    return jsonify({'seats': [seat.to_dict() for seat in seats]}), 200
