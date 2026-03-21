from flask import Blueprint, current_app, jsonify, request
import stripe

bp = Blueprint('stripe_wrapper', __name__)


def _validation_error(message):
    return jsonify({'error': {'code': 'VALIDATION_ERROR', 'message': message}}), 400


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'}), 200


@bp.post('/stripe/create-payment-intent')
def create_payment_intent():
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


@bp.post('/stripe/webhook')
def stripe_webhook():
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
