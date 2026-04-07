from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from app import db
from models import User, PasswordResetToken

bp = Blueprint('users', __name__)


def error_response(status_code: int, code: str, message: str) -> Tuple[dict, int]:
    return jsonify({'error': {'code': code, 'message': message}}), status_code


REQUIRED_FIELDS = ('email', 'password', 'salt', 'phoneNumber')
UPDATABLE_FIELDS = {'email', 'password', 'salt', 'phoneNumber', 'role', 'isFlagged', 'venueId'}


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


@bp.get('/users')
def list_users():
    """
    List all users
    ---
    tags:
      - Users
    responses:
      200:
        description: Array of users
        schema:
          type: array
          items:
            $ref: '#/definitions/User'
    definitions:
      User:
        type: object
        properties:
          userId:
            type: string
            format: uuid
          email:
            type: string
            format: email
          phoneNumber:
            type: string
          role:
            type: string
            enum: [user, admin]
          isFlagged:
            type: boolean
          venueId:
            type: string
            format: uuid
          favoriteEvents:
            type: array
            items:
              type: string
              format: uuid
          createdAt:
            type: string
            format: date-time
          updatedAt:
            type: string
            format: date-time
      Pagination:
        type: object
        properties:
          page:
            type: integer
          limit:
            type: integer
          total:
            type: integer
    """
    users = User.query.order_by(User.createdAt.asc()).all()
    return jsonify([user.to_dict() for user in users]), 200


@bp.post('/users')
def create_user():
    """
    Create a user
    ---
    tags:
      - Users
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [email, password, salt, phoneNumber]
          properties:
            email:
              type: string
              format: email
            password:
              type: string
              description: Pre-hashed password
            salt:
              type: string
            phoneNumber:
              type: string
              description: E.164 format
            role:
              type: string
              enum: [user, admin]
              default: user
            isFlagged:
              type: boolean
              default: false
            venueId:
              type: string
              format: uuid
    responses:
      201:
        description: User created
        schema:
          $ref: '#/definitions/User'
      400:
        description: Missing required fields
      409:
        description: Email already registered
    """
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


@bp.get('/users/<user_id>')
def get_user(user_id):
    """
    Get user by ID (includes sensitive fields)
    ---
    tags:
      - Users
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
    responses:
      200:
        description: User with password and salt (internal use)
        schema:
          $ref: '#/definitions/User'
      404:
        description: User not found
    """
    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, 'USER_NOT_FOUND', 'User not found')
    return jsonify(user.to_dict(include_sensitive=True)), 200


@bp.patch('/users/<user_id>')
def update_user(user_id):
    """
    Update user
    ---
    tags:
      - Users
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            email:
              type: string
              format: email
            password:
              type: string
            salt:
              type: string
            phoneNumber:
              type: string
            role:
              type: string
              enum: [user, admin]
            isFlagged:
              type: boolean
            venueId:
              type: string
              format: uuid
    responses:
      200:
        description: Updated user (includes sensitive fields)
        schema:
          $ref: '#/definitions/User'
      400:
        description: Unsupported fields
      404:
        description: User not found
      409:
        description: Email already registered
    """
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


@bp.get('/users/by-email/<path:email>')
def get_user_by_email(email):
    """
    Get user by email (includes sensitive fields)
    ---
    tags:
      - Users
    parameters:
      - in: path
        name: email
        type: string
        required: true
    responses:
      200:
        description: User with password and salt (internal use)
        schema:
          $ref: '#/definitions/User'
      404:
        description: User not found
    """
    user = User.query.filter_by(email=email).first()
    if not user:
        return error_response(404, 'USER_NOT_FOUND', 'User not found')
    return jsonify(user.to_dict(include_sensitive=True)), 200


@bp.get('/users/<user_id>/favorites')
def get_user_favorites(user_id):
    """
    Get favorite events for a user
    ---
    tags:
      - Favorites
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
    responses:
      200:
        description: List of favorite event IDs
        schema:
          type: object
          properties:
            data:
              type: object
              properties:
                eventIds:
                  type: array
                  items:
                    type: string
                    format: uuid
      404:
        description: User not found
    """
    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, 'USER_NOT_FOUND', 'User not found')
    return jsonify({'data': {'eventIds': user.favoriteEvents or []}}), 200


@bp.put('/users/<user_id>/favorites')
def update_user_favorites(user_id):
    """
    Replace favorite events for a user
    ---
    tags:
      - Favorites
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [eventIds]
          properties:
            eventIds:
              type: array
              items:
                type: string
                format: uuid
    responses:
      200:
        description: Updated favorites
        schema:
          type: object
          properties:
            data:
              type: object
              properties:
                eventIds:
                  type: array
                  items:
                    type: string
                    format: uuid
      400:
        description: Missing or invalid eventIds
      404:
        description: User not found
    """
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


@bp.patch('/admin/users/<user_id>/flag')
def admin_flag_user(user_id):
    """
    Flag or unflag a user (admin)
    ---
    tags:
      - Admin Users
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [isFlagged]
          properties:
            isFlagged:
              type: boolean
            reason:
              type: string
    responses:
      200:
        description: Updated user
        schema:
          $ref: '#/definitions/User'
      400:
        description: Missing isFlagged
      404:
        description: User not found
    """
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


@bp.get('/admin/users')
def admin_list_users():
    """
    List users with optional flag filter (admin)
    ---
    tags:
      - Admin Users
    parameters:
      - in: query
        name: flagged
        type: string
        enum: ['true', 'false']
        description: Filter to flagged or non-flagged users
    responses:
      200:
        description: Array of users
        schema:
          type: array
          items:
            $ref: '#/definitions/User'
    """
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
    Initiate password reset
    ---
    tags:
      - Auth
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [email]
          properties:
            email:
              type: string
              format: email
    responses:
      200:
        description: Reset token generated (dev — token returned in response; use email in production)
        schema:
          type: object
          properties:
            message:
              type: string
            resetToken:
              type: string
            expiresAt:
              type: string
              format: date-time
      400:
        description: Missing email
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
    Reset password using a reset token
    ---
    tags:
      - Auth
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [token, newPassword, salt]
          properties:
            token:
              type: string
            newPassword:
              type: string
              description: New hashed password
            salt:
              type: string
    responses:
      200:
        description: Password reset successful
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: Invalid/expired token or missing fields
      404:
        description: User not found
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
    Verify whether a reset token is valid
    ---
    tags:
      - Auth
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [token]
          properties:
            token:
              type: string
    responses:
      200:
        description: Token validity result
        schema:
          type: object
          properties:
            valid:
              type: boolean
            reason:
              type: string
              description: Reason if invalid (e.g. expired)
      400:
        description: Missing token
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


@bp.get('/admin/users/flagged')
def list_flagged_users():
    """
    List flagged users (admin, paginated)
    ---
    tags:
      - Admin Users
    parameters:
      - in: query
        name: page
        type: integer
        default: 1
      - in: query
        name: limit
        type: integer
        default: 20
    responses:
      200:
        description: Paginated list of flagged users
        schema:
          type: object
          properties:
            users:
              type: array
              items:
                $ref: '#/definitions/User'
            pagination:
              $ref: '#/definitions/Pagination'
    """
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=20, type=int)

    if page < 1:
        return error_response(400, 'VALIDATION_ERROR', 'page must be >= 1')
    if limit < 1 or limit > 100:
        return error_response(400, 'VALIDATION_ERROR', 'limit must be between 1 and 100')

    query = User.query.filter(User.isFlagged == True)

    total = query.count()
    users = (
        query.order_by(User.createdAt.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return jsonify({
        'users': [u.to_dict() for u in users],
        'pagination': {
            'page': page,
            'limit': limit,
            'total': total,
        },
    }), 200


@bp.patch('/admin/users/<user_id>/unflag')
def admin_unflag_user(user_id: str):
    """
    Unflag a user (admin)
    ---
    tags:
      - Admin Users
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
    responses:
      200:
        description: User unflagged
        schema:
          type: object
          properties:
            message:
              type: string
            user:
              $ref: '#/definitions/User'
      400:
        description: User is not flagged
      404:
        description: User not found
    """
    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, 'USER_NOT_FOUND', 'User not found')

    if not user.isFlagged:
        return error_response(400, 'USER_NOT_FLAGGED', 'User is not flagged')

    user.isFlagged = False
    db.session.commit()

    return jsonify({
        'message': 'User unflagged successfully',
        'user': user.to_dict()
    }), 200


@bp.get('/admin/users/<user_id>')
def admin_get_user(user_id: str):
    """
    Get full user details (admin)
    ---
    tags:
      - Admin Users
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
    responses:
      200:
        description: User details including sensitive fields
        schema:
          $ref: '#/definitions/User'
      404:
        description: User not found
    """
    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, 'USER_NOT_FOUND', 'User not found')

    return jsonify(user.to_dict(include_sensitive=True)), 200


@bp.get('/admin/users/search')
def admin_search_users():
    """
    Search users by email or phone (admin)
    ---
    tags:
      - Admin Users
    parameters:
      - in: query
        name: q
        type: string
        required: true
        description: Search by email or phone number
      - in: query
        name: page
        type: integer
        default: 1
      - in: query
        name: limit
        type: integer
        default: 20
    responses:
      200:
        description: Matching users
        schema:
          type: object
          properties:
            users:
              type: array
              items:
                $ref: '#/definitions/User'
            pagination:
              $ref: '#/definitions/Pagination'
      400:
        description: Missing search query
    """
    query_param = request.args.get('q', default='', type=str)
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=20, type=int)

    if not query_param:
        return error_response(400, 'VALIDATION_ERROR', 'Search query "q" is required')

    if page < 1:
        return error_response(400, 'VALIDATION_ERROR', 'page must be >= 1')
    if limit < 1 or limit > 100:
        return error_response(400, 'VALIDATION_ERROR', 'limit must be between 1 and 100')

    search_term = f"%{query_param.strip()}%"
    query = User.query.filter(
        (User.email.ilike(search_term)) | (User.phoneNumber.ilike(search_term))
    )

    total = query.count()
    users = (
        query.order_by(User.createdAt.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return jsonify({
        'users': [u.to_dict() for u in users],
        'pagination': {
            'page': page,
            'limit': limit,
            'total': total,
        },
    }), 200
