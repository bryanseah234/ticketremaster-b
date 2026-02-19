from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.user import User

user_bp = Blueprint('users', __name__)

@user_bp.route('/<user_id>', methods=['GET'])
@jwt_required()
def get_user_profile(user_id):
    """
    Get user profile
    ---
    tags:
      - Users
    parameters:
      - in: path
        name: user_id
        required: true
        type: string
    security:
      - Bearer: []
    responses:
      200:
        description: User profile
      403:
        description: Unauthorized to view this profile
      404:
        description: User not found
    """
    current_user_id = get_jwt_identity()
    
    # Optional: Enforce that users can only view their own profile
    # Or allow if admin (Flagged check?)
    # For simplicity, allow user to view own profile.
    if current_user_id != user_id:
         # Depending on requirements, might allow viewing public info of others.
         # But instructions say "Return full user profile". Usually private.
         # So restrict to self.
         return jsonify({'error': 'Unauthorized to view this profile'}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify(user.to_dict()), 200

@user_bp.route('/<user_id>/risk', methods=['GET'])
def get_user_risk(user_id):
    """
    Get user risk status
    ---
    tags:
      - Users
    parameters:
      - in: path
        name: user_id
        required: true
        type: string
    responses:
      200:
        description: User risk status
      404:
        description: User not found
    """
    # This endpoint might be internal-only (called by Orchestrator), so maybe no JWT required?
    # But for security, let's keep it open or require a service-to-service token (out of scope for now).
    # For now, let's leave it public or minimal auth as per instructions "User Service is the authority".
    # Orchestrator calls this.
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    return jsonify({'user_id': str(user.user_id), 'is_flagged': user.is_flagged}), 200
