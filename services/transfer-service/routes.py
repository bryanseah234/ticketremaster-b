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
    expires_at = transfer.expiresAt
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expires_at


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


@bp.post('/transfers')
def create_transfer():
    """
    Create a transfer request
    ---
    tags:
      - Transfers
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [listingId, buyerId, sellerId, creditAmount]
          properties:
            listingId:
              type: string
              format: uuid
            buyerId:
              type: string
              format: uuid
            sellerId:
              type: string
              format: uuid
            creditAmount:
              type: number
            buyerVerificationSid:
              type: string
            sellerVerificationSid:
              type: string
    responses:
      201:
        description: Transfer created
        schema:
          type: object
          properties:
            transferId:
              type: string
              format: uuid
            status:
              type: string
            expiresAt:
              type: string
              format: date-time
            createdAt:
              type: string
              format: date-time
      400:
        description: Missing required fields
    definitions:
      Transfer:
        type: object
        properties:
          transferId:
            type: string
            format: uuid
          listingId:
            type: string
            format: uuid
          buyerId:
            type: string
            format: uuid
          sellerId:
            type: string
            format: uuid
          creditAmount:
            type: number
          status:
            type: string
            enum: [pending_seller_acceptance, seller_accepted, pending_buyer_otp, buyer_otp_verified, pending_seller_otp, completed, cancelled, expired]
          buyerOtpVerified:
            type: boolean
          sellerOtpVerified:
            type: boolean
          buyerVerificationSid:
            type: string
          sellerVerificationSid:
            type: string
          expiresAt:
            type: string
            format: date-time
          completedAt:
            type: string
            format: date-time
          createdAt:
            type: string
            format: date-time
          updatedAt:
            type: string
            format: date-time
    """
    data = request.get_json(silent=True)
    if not data or any(field not in data for field in REQUIRED_FIELDS):
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields')

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
    """
    List transfers by seller
    ---
    tags:
      - Transfers
    parameters:
      - in: query
        name: sellerId
        type: string
        required: true
      - in: query
        name: status
        type: string
        enum: [pending_seller_acceptance, seller_accepted, pending_buyer_otp, buyer_otp_verified, pending_seller_otp, completed, cancelled, expired]
    responses:
      200:
        description: List of transfers
        schema:
          type: object
          properties:
            transfers:
              type: array
              items:
                $ref: '#/definitions/Transfer'
      400:
        description: Missing sellerId
    """
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
    """
    Get transfer details
    ---
    tags:
      - Transfers
    parameters:
      - in: path
        name: transfer_id
        type: string
        required: true
    responses:
      200:
        description: Transfer details (auto-expires if past expiry)
        schema:
          $ref: '#/definitions/Transfer'
      404:
        description: Transfer not found
    """
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
    """
    Update transfer
    ---
    tags:
      - Transfers
    parameters:
      - in: path
        name: transfer_id
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            status:
              type: string
              enum: [pending_seller_acceptance, seller_accepted, pending_buyer_otp, buyer_otp_verified, pending_seller_otp, completed, cancelled, expired]
            buyerOtpVerified:
              type: boolean
            sellerOtpVerified:
              type: boolean
            buyerVerificationSid:
              type: string
            sellerVerificationSid:
              type: string
            completedAt:
              type: string
              format: date-time
    responses:
      200:
        description: Updated transfer
        schema:
          $ref: '#/definitions/Transfer'
      400:
        description: Validation error or transfer expired
      404:
        description: Transfer not found
    """
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
    """
    Cancel a transfer
    ---
    tags:
      - Transfers
    parameters:
      - in: path
        name: transfer_id
        type: string
        required: true
    responses:
      200:
        description: Transfer cancelled
        schema:
          $ref: '#/definitions/Transfer'
      400:
        description: Transfer already in terminal state
      404:
        description: Transfer not found
    """
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
    """
    List pending transfers for a user (buyer or seller)
    ---
    tags:
      - Transfers
    parameters:
      - in: query
        name: userId
        type: string
        required: true
    responses:
      200:
        description: Pending transfers the user is involved in
        schema:
          type: object
          properties:
            transfers:
              type: array
              items:
                $ref: '#/definitions/Transfer'
      400:
        description: Missing userId
    """
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
