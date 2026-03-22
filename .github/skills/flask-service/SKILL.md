---
name: flask-service
description: How to add or update REST endpoints in TicketRemaster Flask services/orchestrators with repo-specific response, health, and routing patterns.
---

# Flask Service Endpoint Pattern

## When to Use

Use this skill when you add or update HTTP endpoints in `services/*` or `orchestrators/*`.

## Project Conventions

- Keep route handlers in `routes.py` for each module.
- Keep app bootstrap in `app.py`.
- Expose `GET /health` for every service and orchestrator.
- Return JSON responses consistently and include stable error codes on failures.
- Keep module-specific dependencies in local `requirements.txt`.

## Step-by-Step

### 1. Add endpoint in `routes.py`

```python
from flask import Blueprint, jsonify, request

bp = Blueprint("tickets", __name__)

@bp.get("/tickets/<ticket_id>")
def get_ticket(ticket_id):
    return jsonify({"ticketId": ticket_id}), 200
```

### 2. Register blueprint in `app.py`

```python
def create_app():
    app = Flask(__name__)
    from routes import bp
    app.register_blueprint(bp)
    return app
```

### 3. Keep success and error shape predictable

```python
return jsonify({"data": result}), 200
```

```python
return jsonify({
    "error": {
        "code": "RESOURCE_NOT_FOUND",
        "message": "Ticket not found."
    }
}), 404
```

See [../error-handling/SKILL.md](../error-handling/SKILL.md).

### 4. Keep health endpoint explicit

```python
@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "ticket-service"}), 200
```

### 5. Wire tests and compose checks

- Add/extend pytest cases in module `tests/`.
- Verify route works with service-specific README command.
- Add request to shared Postman collection when endpoint is externally tested.

## References

- [../../../services/README.md](../../../services/README.md)
- [../../../orchestrators/README.md](../../../orchestrators/README.md)
- [../../../TESTING.md](../../../TESTING.md)
- [../../../INSTRUCTION.md](../../../INSTRUCTION.md)
