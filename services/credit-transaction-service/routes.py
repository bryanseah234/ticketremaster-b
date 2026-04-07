from flask import Blueprint, jsonify, request

from app import db
from models import CreditTransaction

bp = Blueprint('credit_transactions', __name__)


REQUIRED_FIELDS = ('userId', 'delta', 'reason')


def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code


@bp.get('/health')
def health_check():
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


@bp.post('/credit-transactions')
def create_credit_transaction():
    """
    Create a credit transaction
    ---
    tags:
      - Credit Transactions
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [userId, delta, reason]
          properties:
            userId:
              type: string
              format: uuid
            delta:
              type: number
              description: Positive to credit, negative to debit
            reason:
              type: string
            referenceId:
              type: string
    responses:
      201:
        description: Transaction created
        schema:
          $ref: '#/definitions/CreditTransaction'
      400:
        description: Missing required fields
    """
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
    """
    List credit transactions for a user
    ---
    tags:
      - Credit Transactions
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
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
        description: Paginated list of transactions
        schema:
          type: object
          properties:
            transactions:
              type: array
              items:
                $ref: '#/definitions/CreditTransaction'
            pagination:
              $ref: '#/definitions/Pagination'
    """
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
    """
    Get credit transaction by reference ID
    ---
    tags:
      - Credit Transactions
    parameters:
      - in: path
        name: reference_id
        type: string
        required: true
    responses:
      200:
        description: Transaction found
        schema:
          $ref: '#/definitions/CreditTransaction'
      404:
        description: Transaction not found
    definitions:
      CreditTransaction:
        type: object
        properties:
          txnId:
            type: string
            format: uuid
          userId:
            type: string
            format: uuid
          delta:
            type: number
          reason:
            type: string
          referenceId:
            type: string
          createdAt:
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
