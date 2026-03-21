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

    if 'SMU_API_URL' not in app.config:
        smu_api_url = os.getenv('SMU_API_URL')
        if not smu_api_url:
            raise RuntimeError('SMU_API_URL must be set for otp-wrapper.')
        app.config['SMU_API_URL'] = smu_api_url

    if 'SMU_API_KEY' not in app.config:
        smu_api_key = os.getenv('SMU_API_KEY')
        if not smu_api_key:
            raise RuntimeError('SMU_API_KEY must be set for otp-wrapper.')
        app.config['SMU_API_KEY'] = smu_api_key

    from routes import bp as otp_wrapper_bp

    app.register_blueprint(otp_wrapper_bp)

    @app.get('/health')
    def health_check():
        return jsonify({'status': 'ok'}), 200

    return app


app = None
if os.getenv('SMU_API_URL') and os.getenv('SMU_API_KEY'):
    app = create_app()
