---
name: flask-service
description: How to add REST endpoints to any Flask-based microservice (User, Order, Event, Orchestrator). Covers app factory, blueprints, health checks, Flasgger docs, and standard response format.
---

# Adding REST Endpoints to a Flask Service

## When to Use

Use this skill when adding a new REST endpoint to any of the Flask services: `user-service`, `order-service`, `event-service`, or `orchestrator-service`.

## Project Conventions

- Every service uses the **app factory pattern** (`create_app()` in `src/app.py`)
- Routes are organised into **Flask Blueprints** (one per domain area)
- All responses follow the **standard envelope** from `API.md` Section 2
- All endpoints must have **Flasgger YAML docstrings** for Swagger UI
- Dependencies are pinned in `requirements.txt` with exact versions
- Formatting: `black` (line length 88), linting: `flake8`, imports: `isort`

## Step-by-Step

### 1. Create or edit the Blueprint file

Blueprints live in `src/routes/` (orchestrator) or directly in `src/app.py` (simpler services).

```python
# Example: orchestrator-service/src/routes/purchase_routes.py
from flask import Blueprint, jsonify, request

purchase_bp = Blueprint("purchase", __name__)

@purchase_bp.route("/api/reserve", methods=["POST"])
def reserve_seat():
    """
    Reserve a seat for checkout
    ---
    tags:
      - Purchase Flow
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - seat_id
            - user_id
          properties:
            seat_id:
              type: string
              format: uuid
            user_id:
              type: string
              format: uuid
    responses:
      200:
        description: Seat reserved successfully
      409:
        description: Seat unavailable
    """
    data = request.get_json()
    seat_id = data.get("seat_id")
    user_id = data.get("user_id")

    # Business logic here...

    return jsonify({
        "success": True,
        "data": {
            "order_id": "...",
            "seat_id": seat_id,
            "status": "HELD",
            "held_until": "...",
            "ttl_seconds": 300,
            "message": "Seat reserved. Complete payment within 5 minutes."
        }
    }), 200
```

### 2. Register the Blueprint in `app.py`

```python
def create_app():
    app = Flask(__name__)

    from src.routes.purchase_routes import purchase_bp
    app.register_blueprint(purchase_bp)

    return app
```

### 3. Standard Response Format

Always use this envelope:

```python
# Success
return jsonify({"success": True, "data": {...}}), 200

# Error
return jsonify({
    "success": False,
    "error_code": "SEAT_UNAVAILABLE",
    "message": "This seat is currently held by another user."
}), 409
```

See `error-handling` skill for the full error code reference.

### 4. Health Check Pattern

Every service MUST expose `GET /health`:

```python
@app.route("/health")
def health():
    # Check downstream dependencies
    db_ok = check_db_connection()
    return jsonify({
        "status": "healthy" if db_ok else "unhealthy",
        "service": "user-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {"database": "connected" if db_ok else "disconnected"},
    }), 200 if db_ok else 503
```

### 5. Dockerfile Pattern

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
EXPOSE <port>
CMD ["python", "-m", "src.app"]
```

| Service | Port |
|---|---|
| User Service | 5000 |
| Order Service | 5001 |
| Event Service | 5002 |
| Orchestrator | 5003 |

## References

- `API.md` — Full endpoint contracts and error codes
- `CONTRIBUTING.md` — Code conventions
- `INSTRUCTIONS.md` Section 13 — Flasgger/Swagger setup
