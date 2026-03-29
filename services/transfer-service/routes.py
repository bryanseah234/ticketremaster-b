from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app import db
from models import Transfer

bp = Blueprint('transfers', __name__)

REQUIRED_FIELDS = ('listingId', 'buyerId', 'sellerId', 'creditAmount')
UPDATABLE_FIELDS = {
    'status',
    'buyerOtpVerified',
    'sellerOtpVerified',
    'buyerVerificationSid',
    'sellerVerificationSid',
    'completedAt',
}

# State machine definition: valid transitions for each status
VALID_STATE_TRANSITIONS = {
    'pending_seller_acceptance': ['seller_accepted', 'cancelled', 'expired'],
    'seller_accepted': ['pending_buyer_otp', 'cancelled', 'expired'],
    'pending_buyer_otp': ['buyer_otp_verified', 'cancelled', 'expired'],
    'buyer_otp_verified': ['pending_seller_otp', 'cancelled', 'expired'],
    'pending_seller_otp': ['completed', 'cancelled', 'expired'],
    'completed': [],  # terminal state
    'cancelled': [],  # terminal state
    'expired': [],    # terminal state
}

# Statuses that require buyer OTP verification before proceeding
BUYER_OTP_REQUIRED_STATUSES = {'pending_buyer_otp'}

# Statuses that require seller OTP verification before proceeding
SELLER_OTP_REQUIRED_STATUSES = {'pending_seller_otp'}


def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code


def parse_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    raise ValueError('Invalid datetime format')


def is_transfer_expired(transfer):
    """Check if a transfer has expired."""
    if transfer.expiresAt is None:
        return False
    return datetime.now(timezone.utc) > transfer.expiresAt


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'}), 200


@bp.post('/transfers')
def create_transfer():
    data = request.get_json(silent=True)
    if not data or any(field not in data for field in REQUIRED_FIELDS):
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields')

    # Always start with pending_seller_acceptance - enforce strict state ordering
    # Buyer OTP must come first (steps 5-8), then seller notification (steps 9-13)
    transfer = Transfer(
        listingId=data['listingId'],
        buyerId=data['buyerId'],
        sellerId=data['sellerId'],
        creditAmount=data['creditAmount'],
        status='pending_seller_acceptance',
        buyerVerificationSid=data.get('buyerVerificationSid'),
        sellerVerificationSid=data.get('sellerVerificationSid'),
    )

    db.session.add(transfer)
    db.session.commit()

    return jsonify(
        {
            'transferId': transfer.transferId,
            'status': transfer.status,
            'expiresAt': transfer.expiresAt.isoformat() if transfer.expiresAt else None,
            'createdAt': transfer.createdAt.isoformat() if transfer.createdAt else None,
        }
    ), 201


@bp.get('/transfers')
def list_transfers():
    seller_id = request.args.get('sellerId')
    status    = request.args.get('status')
    if not seller_id:
        return error_response(400, 'VALIDATION_ERROR', 'sellerId query param required')
    query = Transfer.query.filter_by(sellerId=seller_id)
    if status:
        query = query.filter_by(status=status)
    transfers = query.order_by(Transfer.createdAt.desc()).all()
    return jsonify({'transfers': [t.to_dict() for t in transfers]}), 200


@bp.get('/transfers/<transfer_id>')
def get_transfer(transfer_id):
    transfer = db.session.get(Transfer, transfer_id)
    if not transfer:
        return error_response(404, 'TRANSFER_NOT_FOUND', 'Transfer not found')

    # Check if transfer has expired and auto-cancel if so
    if is_transfer_expired(transfer) and transfer.status not in ('completed', 'cancelled', 'expired'):
        transfer.status = 'expired'
        db.session.commit()
        return jsonify(transfer.to_dict()), 200

    return jsonify(transfer.to_dict()), 200


@bp.patch('/transfers/<transfer_id>')
def patch_transfer(transfer_id):
    data = request.get_json(silent=True)
    if not data:
        return error_response(400, 'VALIDATION_ERROR', 'Request body is required')

    invalid_fields = set(data.keys()) - UPDATABLE_FIELDS
    if invalid_fields:
        return error_response(400, 'VALIDATION_ERROR', 'Request contains unsupported fields')

    transfer = db.session.get(Transfer, transfer_id)
    if not transfer:
        return error_response(404, 'TRANSFER_NOT_FOUND', 'Transfer not found')

    # Check if transfer has expired
    if is_transfer_expired(transfer) and transfer.status not in ('completed', 'cancelled', 'expired'):
        transfer.status = 'expired'
        db.session.commit()
        return error_response(400, 'TRANSFER_EXPIRED', 'Transfer has expired')

    # Validate state transitions if status is being updated
    if 'status' in data:
        new_status = data['status']
        current_status = transfer.status

        # Check if the transition is valid
        if current_status not in VALID_STATE_TRANSITIONS:
            return error_response(400, 'INVALID_STATE', f'Unknown current status: {current_status}')

        allowed_transitions = VALID_STATE_TRANSITIONS.get(current_status, [])
        if new_status not in allowed_transitions:
            return error_response(
                400,
                'INVALID_STATE_TRANSITION',
                f'Cannot transition from {current_status} to {new_status}. Allowed transitions: {allowed_transitions}'
            )

        # Enforce buyer OTP verification before seller OTP phase
        if new_status == 'pending_seller_otp' and not transfer.buyerOtpVerified:
            return error_response(
                400,
                'BUYER_OTP_REQUIRED',
                'Buyer must verify OTP before proceeding to seller OTP verification'
            )

        # Enforce seller OTP verification before completion
        if new_status == 'completed' and not transfer.sellerOtpVerified:
            return error_response(
                400,
                'SELLER_OTP_REQUIRED',
                'Seller must verify OTP before completing the transfer'
            )

    if 'completedAt' in data:
        try:
            data['completedAt'] = parse_datetime(data['completedAt'])
        except (ValueError, TypeError):
            return error_response(400, 'VALIDATION_ERROR', 'Invalid completedAt format')

    for field, value in data.items():
        setattr(transfer, field, value)

    db.session.commit()
    return jsonify(transfer.to_dict()), 200


@bp.post('/transfers/<transfer_id>/cancel')
def cancel_transfer(transfer_id):
    """Explicitly cancel a transfer."""
    transfer = db.session.get(Transfer, transfer_id)
    if not transfer:
        return error_response(404, 'TRANSFER_NOT_FOUND', 'Transfer not found')

    if transfer.status in ('completed', 'cancelled', 'expired'):
        return error_response(400, 'INVALID_STATE', f'Cannot cancel transfer in {transfer.status} status')

    transfer.status = 'cancelled'
    db.session.commit()
    return jsonify(transfer.to_dict()), 200


@bp.get('/transfers/pending')
def list_pending_transfers():
    """Get all pending transfers for a user (buyer or seller)."""
    user_id = request.args.get('userId')
    if not user_id:
        return error_response(400, 'VALIDATION_ERROR', 'userId query param required')

    pending_statuses = [
        'pending_seller_acceptance',
        'seller_accepted',
        'pending_buyer_otp',
        'buyer_otp_verified',
        'pending_seller_otp',
    ]

    transfers = Transfer.query.filter(
        ((Transfer.buyerId == user_id) | (Transfer.sellerId == user_id)) &
        Transfer.status.in_(pending_statuses)
    ).order_by(Transfer.createdAt.desc()).all()

    return jsonify({'transfers': [t.to_dict() for t in transfers]}), 200
