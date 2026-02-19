from flask import Flask
from flasgger import Swagger
from src.extensions import db, jwt
import os
from src.models.user import User # Register model

def create_app():
    app = Flask(__name__)
    
    # Configuration
    db_user = os.environ.get('DB_USER', 'user_svc_user')
    db_pass = os.environ.get('DB_PASS', 'password')
    db_host = os.environ.get('DB_HOST', 'users-db')
    db_name = os.environ.get('DB_NAME', 'users_db')
    
    app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{db_user}:{db_pass}@{db_host}/{db_name}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET', 'dev-secret-change-me')
    
    # Initialize Extensions
    db.init_app(app)
    jwt.init_app(app)
    
    from src.extensions import BLOCKLIST
    @jwt.token_in_blocklist_loader
    def check_if_token_in_blocklist(jwt_header, jwt_payload):
        return jwt_payload['jti'] in BLOCKLIST

    Swagger(app)
    
    # Register Blueprints
    from src.routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    
    from src.routes.user import user_bp
    app.register_blueprint(user_bp, url_prefix='/users')

    from src.routes.credits import credits_bp
    app.register_blueprint(credits_bp, url_prefix='/credits')

    from src.routes.otp import otp_bp
    app.register_blueprint(otp_bp, url_prefix='/otp')

    from src.routes.webhooks import webhooks_bp
    app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')

    @app.route('/health')
    def health():
        try:
            db.session.execute(db.text('SELECT 1'))
            return {"service": "user-service", "status": "healthy"}, 200
        except Exception as e:
            return {"service": "user-service", "status": "unhealthy", "error": str(e)}, 503

    print(app.url_map)
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000)
