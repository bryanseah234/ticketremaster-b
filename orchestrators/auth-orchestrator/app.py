from flask import Flask, jsonify
from dotenv import load_dotenv
from flasgger import Swagger


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.update(
        JSON_SORT_KEYS=False,
        TESTING=False,
    )
    if test_config:
        app.config.update(test_config)

    app.config["SWAGGER"] = {
        "title": "Auth Orchestrator",
        "uiversion": 3,
        "version": "1.0.0",
        "description": "Authentication — register, login, and JWT profile.",
        "securityDefinitions": {
            "BearerAuth": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "Enter: Bearer <your_token>",
            }
        },
    }
    Swagger(app)    

    from routes import bp
    app.register_blueprint(bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "auth-orchestrator"}), 200

    return app


app = create_app()
