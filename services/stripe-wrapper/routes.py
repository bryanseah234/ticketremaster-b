from flask import Blueprint, current_app, jsonify, request
import stripe

bp = Blueprint('stripe_wrapper', __name__)


def _validation_error(message):
    return jsonify({'error': {'code': 'VALIDATION_ERROR', 'message': message}}), 400


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


@bp.post('/stripe/create-payment-intent')
def create_payment_intent():
    """
    Create a Stripe payment intent
    ---
    tags:
      - Payments
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [amount, userId]
          properties:
            amount:
              type: integer
              description: Amount in credits (positive integer). Converted to cents internally.
              example: 50
            userId:
              type: string
              format: uuid
    responses:
      200:
        description: Payment intent created
        schema:
          type: object
          properties:
            clientSecret:
              type: string
              description: Stripe client secret — pass to Stripe.js on the frontend
            paymentIntentId:
              type: string
            amount:
              type: integer
              description: Credits being purchased
      400:
        description: Missing or invalid fields
    """
    payload = request.get_json(silent=True) or {}
    amount = payload.get('amount')
    user_id = payload.get('userId')

    if amount is None or user_id is None:
        return _validation_error('amount and userId are required.')

    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        return _validation_error('amount must be a positive integer.')

    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    intent = stripe.PaymentIntent.create(
        amount=amount * 100,
        currency='sgd',
        metadata={
            'userId': str(user_id),
            'credits': str(amount),
        },
    )

    return (
        jsonify(
            {
                'clientSecret': intent.client_secret,
                'paymentIntentId': intent.id,
                'amount': amount,
            }
        ),
        200,
    )


@bp.post('/stripe/retrieve-payment-intent')
def retrieve_payment_intent():
    """
    Retrieve payment intent status
    ---
    tags:
      - Payments
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [paymentIntentId]
          properties:
            paymentIntentId:
              type: string
    responses:
      200:
        description: Payment intent details
        schema:
          type: object
          properties:
            userId:
              type: string
              format: uuid
            credits:
              type: string
              description: Number of credits being purchased
            paymentIntentId:
              type: string
            status:
              type: string
              description: Stripe payment status
      400:
        description: Missing paymentIntentId or payment not succeeded
    """
    payload = request.get_json(silent=True) or {}
    payment_intent_id = payload.get('paymentIntentId')
    if not payment_intent_id:
        return _validation_error('paymentIntentId is required.')

    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    intent = stripe.PaymentIntent.retrieve(payment_intent_id)

    if intent.get('status') != 'succeeded':
        return jsonify({'error': {'code': 'PAYMENT_NOT_SUCCEEDED', 'message': 'Payment has not succeeded.'}}), 400

    metadata = intent.get('metadata', {})
    return jsonify({
        'userId': metadata.get('userId'),
        'credits': metadata.get('credits'),
        'paymentIntentId': intent.get('id'),
        'status': intent.get('status'),
    }), 200


@bp.post('/stripe/webhook')
def stripe_webhook():
    """
    Stripe webhook handler
    ---
    tags:
      - Webhooks
    parameters:
      - in: header
        name: Stripe-Signature
        type: string
        required: true
        description: Stripe webhook signature for verification
      - in: body
        name: body
        required: true
        schema:
          type: object
          description: Raw Stripe event payload
    responses:
      200:
        description: Webhook processed
        schema:
          type: object
          properties:
            received:
              type: boolean
            userId:
              type: string
              format: uuid
            credits:
              type: string
            paymentIntentId:
              type: string
      400:
        description: Invalid signature
    """
    payload = request.get_data(cache=False, as_text=False)
    signature = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']

    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
    except Exception as exc:
        return (
            jsonify(
                {
                    'error': {
                        'code': 'INVALID_SIGNATURE',
                        'message': str(exc),
                    }
                }
            ),
            400,
        )

    response = {'received': True}

    if event.get('type') == 'payment_intent.succeeded':
        payment_intent = event.get('data', {}).get('object', {})
        metadata = payment_intent.get('metadata', {})
        response.update(
            {
                'userId': metadata.get('userId'),
                'credits': metadata.get('credits'),
                'paymentIntentId': payment_intent.get('id'),
            }
        )

    return jsonify(response), 200
