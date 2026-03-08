from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

logger = logging.getLogger("orchestrator")
transfer_bp = Blueprint('transfer', __name__, url_prefix='/transfer')

@transfer_bp.route('/initiate', methods=['POST'])
@jwt_required()
def initiate_transfer():
    from src.orchestrators.transfer_orchestrator import handle_initiate
    data = request.get_json() or {}
    initiator_id = get_jwt_identity()
    seat_id = data.get('seat_id')
    seller_user_id = data.get('seller_user_id')
    buyer_user_id = data.get('buyer_user_id')
    credits_amount = data.get('credits_amount')

    if not seat_id or not seller_user_id or not buyer_user_id or credits_amount is None:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "Missing fields"}), 400

    return handle_initiate(initiator_id, seat_id, seller_user_id, buyer_user_id, credits_amount)

@transfer_bp.route('/confirm', methods=['POST'])
@jwt_required()
def confirm_transfer():
    from src.orchestrators.transfer_orchestrator import handle_confirm
    data = request.get_json() or {}
    user_id = get_jwt_identity()
    transfer_id = data.get('transfer_id')
    seller_otp = data.get('seller_otp')
    buyer_otp = data.get('buyer_otp')

    if not transfer_id or not seller_otp or not buyer_otp:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "Missing fields"}), 400

    return handle_confirm(transfer_id, seller_otp, buyer_otp, user_id)

@transfer_bp.route('/dispute', methods=['POST'])
@jwt_required()
def dispute_transfer():
    from src.orchestrators.transfer_orchestrator import handle_dispute
    data = request.get_json() or {}
    user_id = get_jwt_identity()
    transfer_id = data.get('transfer_id')
    reason = data.get('reason')

    if not transfer_id or not reason:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "Missing fields"}), 400

    return handle_dispute(transfer_id, reason, user_id)

@transfer_bp.route('/reverse', methods=['POST'])
@jwt_required()
def reverse_transfer():
    from src.orchestrators.transfer_orchestrator import handle_reverse
    data = request.get_json() or {}
    user_id = get_jwt_identity()
    transfer_id = data.get('transfer_id')

    if not transfer_id:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "Missing fields"}), 400

    return handle_reverse(transfer_id, user_id)
