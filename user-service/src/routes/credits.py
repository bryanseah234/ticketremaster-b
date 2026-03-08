import stripe
import os

from flask import Blueprint, request, jsonify
from src.models.user import User
from src.models.transaction import CreditTransaction
from src.extensions import db
from decimal import Decimal
import uuid

credits_bp = Blueprint('credits', __name__)

# ... (existing routes)

@credits_bp.route('/escrow/hold', methods=['POST'])
def escrow_hold():
    """
    Deduct credits from buyer and hold in escrow (PENDING transaction)
    """
    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount')
    reference_id = data.get('reference_id') # listing_id
    description = data.get('description', 'Escrow hold for marketplace purchase')

    if not user_id or amount is None or amount <= 0:
        return jsonify({'error': 'Invalid input'}), 400

    try:
        user = User.query.with_for_update().get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if user.credit_balance < Decimal(amount):
            return jsonify({'error': 'Insufficient credits'}), 402

        # 1. Deduct from balance
        user.credit_balance -= Decimal(amount)

        # 2. Record Transaction
        txn = CreditTransaction(
            user_id=user_id,
            amount=amount,
            type='ESCROW_HOLD',
            status='PENDING',
            reference_id=reference_id,
            description=description
        )
        db.session.add(txn)
        db.session.commit()

        return jsonify({
            'message': 'Credits held in escrow',
            'transaction_id': str(txn.transaction_id),
            'remaining_balance': float(user.credit_balance)
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@credits_bp.route('/escrow/release', methods=['POST'])
def escrow_release():
    """
    Release held credits to the seller
    """
    data = request.get_json()
    transaction_id = data.get('transaction_id')
    seller_user_id = data.get('seller_user_id')

    if not transaction_id or not seller_user_id:
        return jsonify({'error': 'Missing transaction_id or seller_user_id'}), 400

    try:
        txn = CreditTransaction.query.with_for_update().get(transaction_id)
        if not txn:
            return jsonify({'error': 'Transaction not found'}), 404
        
        if txn.type != 'ESCROW_HOLD' or txn.status != 'PENDING':
            return jsonify({'error': 'Invalid transaction state for release'}), 400

        seller = User.query.with_for_update().get(seller_user_id)
        if not seller:
            return jsonify({'error': 'Seller not found'}), 404

        # 1. Update Seller Balance
        seller.credit_balance += txn.amount

        # 2. Update Transaction Status
        txn.status = 'COMPLETED'
        
        # 3. Create a secondary transaction record for the seller?
        # For simplicity, we just complete the first one and maybe add a second one later.
        
        db.session.commit()

        return jsonify({
            'message': 'Credits released to seller',
            'seller_new_balance': float(seller.credit_balance)
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

@credits_bp.route('/topup', methods=['POST'])
def topup_credits():
    """
    Top-up user credits (Stripe PaymentIntent)
    ---
    tags:
      - Credits
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - user_id
            - amount
          properties:
            user_id:
              type: string
            amount:
              type: number
    responses:
      200:
        description: PaymentIntent created
      404:
        description: User not found
      400:
        description: Invalid amount
    """
    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount')
    
    if not user_id or amount is None or amount <= 0:
        return jsonify({'error': 'Invalid input'}), 400
        
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    try:
        # Create a PaymentIntent with the order amount (in cents) and currency
        intent = stripe.PaymentIntent.create(
            amount=int(Decimal(amount) * 100),
            currency='sgd',
            metadata={'user_id': user_id, 'topup_amount': float(amount)},
            automatic_payment_methods={
                'enabled': True,
            },
        )
        return jsonify({
            'message': 'PaymentIntent created',
            'client_secret': intent.client_secret,
            'amount': amount
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@credits_bp.route('/deduct', methods=['POST'])
def deduct_credits():
    """
    Deduct user credits atomically
    ---
    tags:
      - Credits
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - user_id
            - amount
          properties:
            user_id:
              type: string
            amount:
              type: number
    responses:
      200:
        description: Deduction successful
      402:
        description: Insufficient credits
      404:
        description: User not found
    """
    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount')
    
    if not user_id or amount is None or amount <= 0:
        return jsonify({'error': 'Invalid input'}), 400
        
    try:
        # SELECT FOR UPDATE to lock the row
        user = User.query.with_for_update().get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        if user.credit_balance < Decimal(amount):
            return jsonify({'error': 'Insufficient credits', 'current_balance': float(user.credit_balance)}), 402
            
        user.credit_balance -= Decimal(amount)
        db.session.commit()
        return jsonify({'message': 'Deduction successful', 'new_balance': float(user.credit_balance)}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@credits_bp.route('/refund', methods=['POST'])
def refund_credits():
    """
    Refund user credits atomically
    ---
    tags:
      - Credits
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - user_id
            - amount
          properties:
            user_id:
              type: string
            amount:
              type: number
    responses:
      200:
        description: Refund successful
      404:
        description: User not found
    """
    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount')
    
    if not user_id or amount is None or amount <= 0:
        return jsonify({'error': 'Invalid input'}), 400
        
    try:
        # SELECT FOR UPDATE to lock the row
        user = User.query.with_for_update().get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        user.credit_balance += Decimal(amount)
        db.session.commit()
        return jsonify({'message': 'Refund successful', 'new_balance': float(user.credit_balance)}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@credits_bp.route('/transfer', methods=['POST'])
def transfer_credits():
    """
    Transfer credits between users atomically
    ---
    tags:
      - Credits
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - from_user_id
            - to_user_id
            - amount
          properties:
            from_user_id:
              type: string
            to_user_id:
              type: string
            amount:
              type: number
    responses:
      200:
        description: Transfer successful
      400:
        description: Invalid input
      402:
        description: Insufficient credits
      404:
        description: User not found
    """
    data = request.get_json()
    from_user_id = data.get('from_user_id')
    to_user_id = data.get('to_user_id')
    amount = data.get('amount')
    
    if not from_user_id or not to_user_id or amount is None or amount <= 0:
        return jsonify({'error': 'Invalid input'}), 400
        
    if from_user_id == to_user_id:
        return jsonify({'error': 'Cannot transfer to self'}), 400
        
    try:
        # Sort user IDs to prevent deadlocks when locking multiple rows
        first_id, second_id = sorted([from_user_id, to_user_id])
        
        # Lock both rows
        # We need to fetch them in order
        u1 = User.query.with_for_update().get(first_id)
        u2 = User.query.with_for_update().get(second_id)
        
        if not u1 or not u2:
            return jsonify({'error': 'One or both users not found'}), 404
            
        # Identify sender and receiver from the locked objects
        sender = u1 if u1.user_id == uuid.UUID(from_user_id) else u2
        receiver = u2 if u2.user_id == uuid.UUID(to_user_id) else u1
        
        if sender.credit_balance < Decimal(amount):
            return jsonify({'error': 'Insufficient credits', 'current_balance': float(sender.credit_balance)}), 402
            
        sender.credit_balance -= Decimal(amount)
        receiver.credit_balance += Decimal(amount)
        
        db.session.commit()
        return jsonify({
            'message': 'Transfer successful',
            'from_user_balance': float(sender.credit_balance),
            'to_user_balance': float(receiver.credit_balance)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
