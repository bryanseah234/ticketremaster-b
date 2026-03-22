# Service Setup Template

This folder provides reusable Dockerfile templates for scaffolding new services with repo-consistent runtime settings.

## Available Templates

- `Dockerfile.service` — default Flask service/orchestrator image template
- `Dockerfile.seat-inventory` — specialized template for seat inventory runtime layout

## Scaffolding Map

### Standard atomic service or orchestrator
- `templates/Dockerfile.service` -> `services/<name>/Dockerfile` or `orchestrators/<name>/Dockerfile`
- `shared/requirements.txt` -> `<module>/requirements.txt`

### Seat inventory service
- `templates/Dockerfile.seat-inventory` -> `services/seat-inventory-service/Dockerfile`
- `shared/requirements.txt` -> `services/seat-inventory-service/requirements.txt`

## Suggested First Files

- `app.py`
- `models.py` for data-owning services
- `routes.py`
- `migrations/` for PostgreSQL-backed services

Orchestrators should also add:
- `middleware.py`
- service-call helper modules for outbound HTTP/gRPC calls

## Related Docs

- Shared dependencies and gRPC assets: [../shared/README.md](../shared/README.md)
- Service index: [../services/README.md](../services/README.md)
- Orchestrator index: [../orchestrators/README.md](../orchestrators/README.md)
- Implementation sequence: [../INSTRUCTION.md](../INSTRUCTION.md)
- Root documentation hub: [../README.md](../README.md)

