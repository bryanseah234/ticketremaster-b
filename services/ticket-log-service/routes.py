from flask import Blueprint, jsonify, request

from app import db
from models import TicketLog

bp = Blueprint('ticket_logs', __name__)

REQUIRED_FIELDS = ('ticketId', 'staffId', 'status')


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


@bp.post('/ticket-logs')
def create_ticket_log():
    """
    Create a ticket log entry
    ---
    tags:
      - Ticket Logs
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [ticketId, staffId, status]
          properties:
            ticketId:
              type: string
              format: uuid
            staffId:
              type: string
              format: uuid
              description: UUID of the staff member performing the action
            status:
              type: string
              description: Status recorded (e.g. used, scanned)
    responses:
      201:
        description: Log entry created
        schema:
          $ref: '#/definitions/TicketLog'
      400:
        description: Missing required fields
    definitions:
      TicketLog:
        type: object
        properties:
          logId:
            type: string
            format: uuid
          ticketId:
            type: string
            format: uuid
          staffId:
            type: string
            format: uuid
          status:
            type: string
          timestamp:
            type: string
            format: date-time
    """
    data = request.get_json(silent=True)
    if not data or any(field not in data for field in REQUIRED_FIELDS):
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields')

    ticket_log = TicketLog(
        ticketId=data['ticketId'],
        staffId=data['staffId'],
        status=data['status'],
    )
    db.session.add(ticket_log)
    db.session.commit()

    return jsonify(ticket_log.to_dict()), 201


@bp.get('/ticket-logs/ticket/<ticket_id>')
def get_ticket_logs_by_ticket_id(ticket_id):
    """
    Get all log entries for a ticket
    ---
    tags:
      - Ticket Logs
    parameters:
      - in: path
        name: ticket_id
        type: string
        required: true
    responses:
      200:
        description: List of log entries (most recent first)
        schema:
          type: object
          properties:
            logs:
              type: array
              items:
                $ref: '#/definitions/TicketLog'
    """
    logs = TicketLog.query.filter_by(ticketId=ticket_id).order_by(TicketLog.timestamp.desc()).all()
    return jsonify({'logs': [ticket_log.to_dict() for ticket_log in logs]}), 200
