import os
from flask import Flask, jsonify
from dotenv import load_dotenv
from flasgger import Swagger

def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.update(JSON_SORT_KEYS=False, TESTING=False)
    if test_config:
        app.config.update(test_config)

    app.config["SWAGGER"] = {
        "title": "Event Orchestrator",
        "uiversion": 3,
        "version": "1.0.0",
        "description": "Public event browsing — no authentication required.",
    }
    Swagger(app)    

    from routes import bp
    app.register_blueprint(bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "event-orchestrator"}), 200

    return app


app = create_app()
