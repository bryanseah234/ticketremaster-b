from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

logger = logging.getLogger("orchestrator")
marketplace_bp = Blueprint('marketplace', __name__)

@marketplace_bp.route('/marketplace/list', methods=['POST'])
@jwt_required()
def list_ticket():
    from src.orchestrators.marketplace_orchestrator import handle_list_ticket
    data = request.get_json() or {}
    user_id = get_jwt_identity()
    seat_id = data.get('seat_id')
    asking_price = data.get('asking_price')

    if not seat_id or asking_price is None:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "seat_id and asking_price are required"}), 400

    return handle_list_ticket(seat_id, user_id, asking_price)

@marketplace_bp.route('/marketplace/listings', methods=['GET'])
@jwt_required()
def get_listings():
    # This route could potentially be public if we want discovered tickets viewable, 
    # but the prompt says "internal discovery for logged in users".
    from src.utils.http_client import order_service
    status = request.args.get('status', 'ACTIVE')
    res = order_service.get(f"/marketplace/listings?status={status}")
    return jsonify(res.json()), res.status_code

@marketplace_bp.route('/marketplace/buy', methods=['POST'])
@jwt_required()
def buy_listing():
    from src.orchestrators.marketplace_orchestrator import handle_buy_listing
    data = request.get_json() or {}
    user_id = get_jwt_identity()
    listing_id = data.get('listing_id')

    if not listing_id:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "listing_id is required"}), 400

    return handle_buy_listing(listing_id, user_id)

@marketplace_bp.route('/marketplace/approve', methods=['POST'])
@jwt_required()
def approve_listing():
    from src.orchestrators.marketplace_orchestrator import handle_approve_listing
    data = request.get_json() or {}
    user_id = get_jwt_identity()
    listing_id = data.get('listing_id')
    otp_code = data.get('otp_code')

    if not listing_id or not otp_code:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "listing_id and otp_code are required"}), 400

    return handle_approve_listing(listing_id, user_id, otp_code)
