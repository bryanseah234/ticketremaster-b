from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt

admin_bp = Blueprint('admin', __name__)

def require_admin():
    claims = get_jwt()
    if not claims.get('is_admin', False):
        return jsonify({"success": False, "error_code": "UNAUTHORIZED", "message": "Admin privileges required"}), 403
    return None

@admin_bp.route('/events', methods=['POST'])
@jwt_required()
def create_event():
    err = require_admin()
    if err: return err

    from src.orchestrators.admin_orchestrator import handle_create_event
    data = request.get_json() or {}
    
    # Required fields Check
    required = ['name', 'venue', 'hall_id', 'event_date', 'total_seats', 'pricing_tiers']
    if not all(k in data for k in required):
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "Missing required fields"}), 400

    return handle_create_event(data)

@admin_bp.route('/events/<event_id>/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard(event_id):
    err = require_admin()
    if err: return err

    from src.orchestrators.admin_orchestrator import handle_get_dashboard
    return handle_get_dashboard(event_id)
