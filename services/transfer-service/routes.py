from datetime import datetime

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


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'}), 200


@bp.post('/transfers')
def create_transfer():
    data = request.get_json(silent=True)
    if not data or any(field not in data for field in REQUIRED_FIELDS):
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields')

    if data.get('sellerVerificationSid'):
        initial_status = 'pending_seller_otp'
    elif data.get('buyerVerificationSid'):
        initial_status = 'pending_buyer_otp'
    else:
        initial_status = 'pending_seller_acceptance'

    transfer = Transfer(
        listingId=data['listingId'],
        buyerId=data['buyerId'],
        sellerId=data['sellerId'],
        creditAmount=data['creditAmount'],
        status=initial_status,
        buyerVerificationSid=data.get('buyerVerificationSid'),
        sellerVerificationSid=data.get('sellerVerificationSid'),
    )

    db.session.add(transfer)
    db.session.commit()

    return jsonify(
        {
            'transferId': transfer.transferId,
            'status': transfer.status,
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

    if 'completedAt' in data:
        try:
            data['completedAt'] = parse_datetime(data['completedAt'])
        except (ValueError, TypeError):
            return error_response(400, 'VALIDATION_ERROR', 'Invalid completedAt format')

    for field, value in data.items():
        setattr(transfer, field, value)

    db.session.commit()
    return jsonify(transfer.to_dict()), 200
