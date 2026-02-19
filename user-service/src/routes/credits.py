from flask import Blueprint, request, jsonify
from src.models.user import User
from src.extensions import db
from decimal import Decimal
import uuid

credits_bp = Blueprint('credits', __name__)

@credits_bp.route('/topup', methods=['POST'])
def topup_credits():
    """
    Top-up user credits (Mock Stripe)
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
        description: Top-up successful
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
        
    # Simulate Stripe payment success here
    # In real world, we'd verify a stripe token/intent
    
    user.credit_balance = (user.credit_balance or 0) + Decimal(amount)
    
    try:
        db.session.commit()
        return jsonify({'message': 'Top-up successful', 'new_balance': float(user.credit_balance)}), 200
    except Exception as e:
        db.session.rollback()
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
