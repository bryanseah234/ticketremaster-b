# Service Setup Template

Use `shared/requirements.txt` as the starting point for each Python service.

Files to copy when scaffolding a standard service:
- `templates/Dockerfile.service` -> `services/<name>/Dockerfile`
- `shared/requirements.txt` -> `services/<name>/requirements.txt`

Files to copy when scaffolding the Seat Inventory Service:
- `templates/Dockerfile.seat-inventory` -> `services/seat-inventory-service/Dockerfile`
- `shared/requirements.txt` -> `services/seat-inventory-service/requirements.txt`

Recommended first files per service:
- `app.py`
- `models.py`
- `routes.py`
- `migrations/`

