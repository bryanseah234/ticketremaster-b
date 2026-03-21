from flask import Blueprint, jsonify, request

from app import db
from models import CreditTransaction

bp = Blueprint('credit_transactions', __name__)


REQUIRED_FIELDS = ('userId', 'delta', 'reason')


def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code


@bp.get('/health')
def health_check():
    return jsonify({'status': 'ok'}), 200


@bp.post('/credit-transactions')
def create_credit_transaction():
    data = request.get_json(silent=True)
    if not data or any(field not in data for field in REQUIRED_FIELDS):
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields')

    transaction = CreditTransaction(
        userId=data['userId'],
        delta=data['delta'],
        reason=data['reason'],
        referenceId=data.get('referenceId'),
    )
    db.session.add(transaction)
    db.session.commit()

    return jsonify(transaction.to_dict()), 201


@bp.get('/credit-transactions/user/<user_id>')
def list_credit_transactions_by_user(user_id):
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=20, type=int)

    if page is None or page < 1:
        return error_response(400, 'VALIDATION_ERROR', 'page must be an integer greater than or equal to 1')
    if limit is None or limit < 1:
        return error_response(400, 'VALIDATION_ERROR', 'limit must be an integer greater than or equal to 1')

    limit = min(limit, 100)

    query = CreditTransaction.query.filter_by(userId=user_id)
    total = query.count()
    transactions = (
        query.order_by(CreditTransaction.createdAt.desc(), CreditTransaction.txnId.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return (
        jsonify(
            {
                'transactions': [transaction.to_dict() for transaction in transactions],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                },
            }
        ),
        200,
    )


@bp.get('/credit-transactions/reference/<reference_id>')
def get_credit_transaction_by_reference(reference_id):
    transaction = (
        CreditTransaction.query.filter_by(referenceId=reference_id)
        .order_by(CreditTransaction.createdAt.desc(), CreditTransaction.txnId.desc())
        .first()
    )
    if not transaction:
        return error_response(
            404,
            'TRANSACTION_NOT_FOUND',
            f'No credit transaction found for referenceId: {reference_id}',
        )

    return jsonify(transaction.to_dict()), 200
