from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

logger = logging.getLogger("orchestrator")
ticket_bp = Blueprint('ticket', __name__, url_prefix='/tickets')

@ticket_bp.route('', methods=['GET'])
@jwt_required()
def get_tickets():
    from src.orchestrators.verification_orchestrator import handle_get_tickets
    user_id = get_jwt_identity()
    return handle_get_tickets(user_id)

@ticket_bp.route('/<seat_id>/qr', methods=['GET'])
@jwt_required()
def generate_qr(seat_id):
    from src.orchestrators.verification_orchestrator import handle_generate_qr
    user_id = get_jwt_identity()
    return handle_generate_qr(seat_id, user_id)
