from flask import Blueprint, jsonify, request

from app import db
from models import TicketLog

bp = Blueprint('ticket_logs', __name__)

REQUIRED_FIELDS = ('ticketId', 'staffId', 'status')


def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'}), 200


@bp.post('/ticket-logs')
def create_ticket_log():
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
    logs = TicketLog.query.filter_by(ticketId=ticket_id).order_by(TicketLog.timestamp.desc()).all()
    return jsonify({'logs': [ticket_log.to_dict() for ticket_log in logs]}), 200
