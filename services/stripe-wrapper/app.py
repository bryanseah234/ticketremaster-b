import os

from dotenv import load_dotenv
from flask import Flask, jsonify

load_dotenv()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        JSON_SORT_KEYS=False,
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

    if 'STRIPE_SECRET_KEY' not in app.config:
        stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
        if not stripe_secret_key:
            raise RuntimeError('STRIPE_SECRET_KEY must be set for stripe-wrapper.')
        app.config['STRIPE_SECRET_KEY'] = stripe_secret_key

    if 'STRIPE_WEBHOOK_SECRET' not in app.config:
        stripe_webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        if not stripe_webhook_secret:
            raise RuntimeError('STRIPE_WEBHOOK_SECRET must be set for stripe-wrapper.')
        app.config['STRIPE_WEBHOOK_SECRET'] = stripe_webhook_secret

    from routes import bp as stripe_wrapper_bp

    app.register_blueprint(stripe_wrapper_bp)

    @app.get('/health')
    def health_check():
        return jsonify({'status': 'ok'}), 200

    return app


app = None
if os.getenv('STRIPE_SECRET_KEY') and os.getenv('STRIPE_WEBHOOK_SECRET'):
    app = create_app()
