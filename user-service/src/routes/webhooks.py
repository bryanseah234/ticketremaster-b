from flask import Blueprint, request, jsonify
import os
import stripe
from src.models.user import User
from src.extensions import db
from decimal import Decimal

webhooks_bp = Blueprint('webhooks', __name__)

STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')
# stripe.api_key = os.environ.get('STRIPE_SECRET_KEY') # Not strictly needed for webhook validation only

@webhooks_bp.route('/stripe', methods=['POST'])
def stripe_webhook():
    """
    Handle Stripe Webhooks
    ---
    tags:
      - Webhooks
    responses:
      200:
        description: Event processed
      400:
        description: Invalid payload or signature
    """
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return jsonify({'error': 'Invalid signature'}), 400

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        handle_payment_succeeded(payment_intent)
    
    # Return a success response to confirm receipt
    return jsonify({'status': 'success'}), 200

def handle_payment_succeeded(payment_intent):
    # Extract customer/user info from metadata
    user_id = payment_intent.get('metadata', {}).get('user_id')
    amount_cents = payment_intent.get('amount', 0)
    
    if not user_id:
        print("Error: No user_id in payment intent metadata")
        return
        
    amount_dollars = Decimal(amount_cents) / 100
    
    try:
        user = User.query.get(user_id)
        if user:
            user.credit_balance = (user.credit_balance or 0) + amount_dollars
            db.session.commit()
            print(f"Successfully added ${amount_dollars} to user {user_id}")
        else:
            print(f"User {user_id} not found for payment {payment_intent['id']}")
    except Exception as e:
        print(f"Database error updating credits: {e}")
        db.session.rollback()
