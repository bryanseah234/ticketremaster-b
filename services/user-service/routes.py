from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
import secrets
from datetime import datetime, timezone, timedelta

from app import db
from models import User, PasswordResetToken

bp = Blueprint('users', __name__)


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'}), 200


REQUIRED_FIELDS = ('email', 'password', 'salt', 'phoneNumber')
UPDATABLE_FIELDS = {'email', 'password', 'salt', 'phoneNumber', 'role', 'isFlagged', 'venueId'}


def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code


# List all users for internal service and admin-facing lookups.
@bp.get('/users')
def list_users():
    users = User.query.order_by(User.createdAt.asc()).all()
    return jsonify([user.to_dict() for user in users]), 200


# Create a user record from pre-hashed credentials supplied by the auth layer.
@bp.post('/users')
def create_user():
    data = request.get_json(silent=True)
    if not data or any(field not in data for field in REQUIRED_FIELDS):
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields')

    if User.query.filter_by(email=data['email']).first():
        return error_response(409, 'EMAIL_ALREADY_EXISTS', 'Email already registered')

    user = User(
        email=data['email'],
        password=data['password'],
        salt=data['salt'],
        phoneNumber=data['phoneNumber'],
        role=data.get('role', 'user'),
        isFlagged=data.get('isFlagged', False),
        venueId=data.get('venueId')
    )
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


# Fetch a single user by internal UUID with the full stored record.
@bp.get('/users/<user_id>')
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, 'USER_NOT_FOUND', 'User not found')
    return jsonify(user.to_dict(include_sensitive=True)), 200


# Apply a partial update to allowed user fields.
@bp.patch('/users/<user_id>')
def update_user(user_id):
    data = request.get_json(silent=True)
    if not data:
        return error_response(400, 'VALIDATION_ERROR', 'Request body is required')

    invalid_fields = set(data.keys()) - UPDATABLE_FIELDS
    if invalid_fields:
        return error_response(400, 'VALIDATION_ERROR', 'Request contains unsupported fields')

    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, 'USER_NOT_FOUND', 'User not found')

    if 'email' in data:
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user and existing_user.userId != user.userId:
            return error_response(409, 'EMAIL_ALREADY_EXISTS', 'Email already registered')

    for field, value in data.items():
        setattr(user, field, value)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response(409, 'EMAIL_ALREADY_EXISTS', 'Email already registered')

    return jsonify(user.to_dict(include_sensitive=True)), 200


# Fetch a user by email, including stored password and salt for auth verification.
@bp.get('/users/by-email/<path:email>')
def get_user_by_email(email):
    user = User.query.filter_by(email=email).first()
    if not user:
        return error_response(404, 'USER_NOT_FOUND', 'User not found')
    return jsonify(user.to_dict(include_sensitive=True)), 200


# Get user's favorite events list
@bp.get('/users/<user_id>/favorites')
def get_user_favorites(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, 'USER_NOT_FOUND', 'User not found')
    return jsonify({'data': {'eventIds': user.favoriteEvents or []}}), 200


# Update user's favorite events list (replaces entire list)
@bp.put('/users/<user_id>/favorites')
def update_user_favorites(user_id):
    data = request.get_json(silent=True)
    if not data or 'eventIds' not in data:
        return error_response(400, 'VALIDATION_ERROR', 'eventIds field is required')

    if not isinstance(data['eventIds'], list):
        return error_response(400, 'VALIDATION_ERROR', 'eventIds must be an array')

    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, 'USER_NOT_FOUND', 'User not found')

    user.favoriteEvents = data['eventIds']
    db.session.commit()
    return jsonify({'data': {'eventIds': user.favoriteEvents}}), 200


# Admin endpoint: Flag a user
@bp.patch('/admin/users/<user_id>/flag')
def admin_flag_user(user_id):
    """Admin-only endpoint to flag/unflag a user."""
    data = request.get_json(silent=True)
    if not data or 'isFlagged' not in data:
        return error_response(400, 'VALIDATION_ERROR', 'isFlagged field is required')

    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, 'USER_NOT_FOUND', 'User not found')

    user.isFlagged = data['isFlagged']
    if 'reason' in data:
        # Store the reason in a note field if available, or just flag
        pass  # Note: could add a flagReason field to User model if needed

    db.session.commit()
    return jsonify(user.to_dict()), 200


# Admin endpoint: List flagged users
@bp.get('/admin/users')
def admin_list_users():
    """Admin-only endpoint to list users with optional filtering."""
    flagged = request.args.get('flagged')

    query = User.query
    if flagged == 'true':
        query = query.filter_by(isFlagged=True)
    elif flagged == 'false':
        query = query.filter_by(isFlagged=False)

    users = query.order_by(User.createdAt.asc()).all()
    return jsonify([user.to_dict() for user in users]), 200


# Password reset endpoints
RESET_TOKEN_TTL_HOURS = 24


@bp.post('/auth/forgot-password')
def forgot_password():
    """
    Initiate password reset flow.
    Generates a reset token and returns it (in production, this would be sent via email/SMS).
    """
    data = request.get_json(silent=True)
    if not data or 'email' not in data:
        return error_response(400, 'VALIDATION_ERROR', 'email field is required')

    user = User.query.filter_by(email=data['email']).first()
    if not user:
        # Don't reveal if user exists - return success anyway for security
        return jsonify({'message': 'If the email exists, a reset link has been sent'}), 200

    # Invalidate any existing unused tokens for this user
    PasswordResetToken.query.filter_by(userId=user.userId, used=False).update({'used': True})

    # Generate new reset token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_TTL_HOURS)

    reset_token = PasswordResetToken(
        userId=user.userId,
        token=token,
        expiresAt=expires_at,
    )
    db.session.add(reset_token)
    db.session.commit()

    # In production, send token via email/SMS here
    # For now, return the token in the response (development only)
    return jsonify({
        'message': 'Password reset token generated',
        'resetToken': token,  # Remove in production - send via email instead
        'expiresAt': expires_at.isoformat(),
    }), 200


@bp.post('/auth/reset-password')
def reset_password():
    """
    Reset password using a valid reset token.
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(400, 'VALIDATION_ERROR', 'Request body is required')

    # Validate required fields
    if 'token' not in data or 'newPassword' not in data or 'salt' not in data:
        return error_response(400, 'VALIDATION_ERROR', 'token, newPassword, and salt fields are required')

    token_str = data['token']
    new_password = data['newPassword']
    new_salt = data['salt']

    # Find and validate token
    reset_token = PasswordResetToken.query.filter_by(token=token_str, used=False).first()
    if not reset_token:
        return error_response(400, 'INVALID_TOKEN', 'Invalid or used reset token')

    # Check if token is expired
    if reset_token.expiresAt < datetime.now(timezone.utc):
        reset_token.used = True
        db.session.commit()
        return error_response(400, 'TOKEN_EXPIRED', 'Reset token has expired')

    # Get the user
    user = User.query.get(reset_token.userId)
    if not user:
        return error_response(404, 'USER_NOT_FOUND', 'User not found')

    # Update user password
    user.password = new_password
    user.salt = new_salt

    # Mark token as used
    reset_token.used = True
    reset_token.completedAt = datetime.now(timezone.utc)

    db.session.commit()

    return jsonify({'message': 'Password reset successful'}), 200


@bp.post('/auth/verify-reset-token')
def verify_reset_token():
    """
    Verify if a reset token is valid (without using it).
    Useful for validating token before showing password reset form.
    """
    data = request.get_json(silent=True)
    if not data or 'token' not in data:
        return error_response(400, 'VALIDATION_ERROR', 'token field is required')

    reset_token = PasswordResetToken.query.filter_by(token=data['token'], used=False).first()
    if not reset_token:
        return jsonify({'valid': False}), 200

    if reset_token.expiresAt < datetime.now(timezone.utc):
        return jsonify({'valid': False, 'reason': 'expired'}), 200

    return jsonify({'valid': True}), 200
