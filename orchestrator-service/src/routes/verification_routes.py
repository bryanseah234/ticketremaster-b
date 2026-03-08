from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

logger = logging.getLogger("orchestrator")
verification_bp = Blueprint('verification', __name__)

@verification_bp.route('/verify', methods=['POST'])
@jwt_required()
def verify_ticket():
    from src.orchestrators.verification_orchestrator import handle_verify
    data = request.get_json() or {}
    staff_id = get_jwt_identity()
    qr_payload = data.get('qr_payload')
    hall_id = data.get('hall_id')
    
    if not qr_payload or not hall_id:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "Missing fields"}), 400

    return handle_verify(qr_payload, hall_id, staff_id)
