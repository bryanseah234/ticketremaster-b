import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JSON_SORT_KEYS=False,
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

    if 'SQLALCHEMY_DATABASE_URI' not in app.config:
        database_url = os.getenv('TICKET_SERVICE_DATABASE_URL') or os.getenv('DATABASE_URL')
        if not database_url:
            raise RuntimeError(
                'TICKET_SERVICE_DATABASE_URL (or DATABASE_URL) must be set for ticket-service.'
            )
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url

    db.init_app(app)
    migrate.init_app(app, db)

    from models import Ticket  # noqa: F401
    from routes import bp as tickets_bp

    app.register_blueprint(tickets_bp)

    @app.get('/health')
    def health_check():
        return jsonify({'status': 'ok'}), 200

    return app


app = None
if os.getenv('TICKET_SERVICE_DATABASE_URL') or os.getenv('DATABASE_URL'):
    app = create_app()
