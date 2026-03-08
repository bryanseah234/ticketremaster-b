from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

logger = logging.getLogger("orchestrator")
purchase_bp = Blueprint('purchase', __name__)

@purchase_bp.route('/reserve', methods=['POST'])
@jwt_required()
def reserve():
    from src.orchestrators.purchase_orchestrator import handle_reserve
    data = request.get_json() or {}
    user_id = get_jwt_identity()
    seat_id = data.get('seat_id')
    event_id = data.get('event_id')

    if not seat_id:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "seat_id is required"}), 400

    return handle_reserve(seat_id, user_id, event_id)

@purchase_bp.route('/pay', methods=['POST'])
@jwt_required()
def pay():
    from src.orchestrators.purchase_orchestrator import handle_pay
    data = request.get_json() or {}
    user_id = get_jwt_identity()
    order_id = data.get('order_id')

    if not order_id:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "order_id is required"}), 400

    return handle_pay(order_id, user_id)

@purchase_bp.route('/verify-otp', methods=['POST'])
@jwt_required()
def verify_otp():
    from src.orchestrators.purchase_orchestrator import handle_verify_otp
    data = request.get_json() or {}
    user_id = get_jwt_identity()
    otp_code = data.get('otp_code')
    context = data.get('context')
    reference_id = data.get('reference_id')

    if not otp_code or not context or not reference_id:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "Missing fields"}), 400

    return handle_verify_otp(user_id, otp_code, context, reference_id)
