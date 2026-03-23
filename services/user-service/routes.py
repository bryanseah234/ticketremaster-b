from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from models import User

bp = Blueprint('users', __name__)


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'}), 200


REQUIRED_FIELDS = ('email', 'password', 'salt', 'phoneNumber')
UPDATABLE_FIELDS = {'email', 'password', 'salt', 'phoneNumber', 'role', 'isFlagged'}


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