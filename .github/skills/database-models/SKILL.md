---
name: database-models
description: TicketRemaster SQLAlchemy and migration conventions for service-owned PostgreSQL schemas, seeding, and concurrency-safe updates.
---

# Database Model Pattern

## When to Use

Use this skill when adding/updating models, migrations, and seed behavior in service folders under `services/*`.

## Architecture Rules

1. One database per service, no cross-service ORM model imports.
2. Use explicit primary keys and stable ID formats consistent with service contracts.
3. Keep migrations in `migrations/` and treat them as source of truth.
4. Keep seeds idempotent so shared team runs are reproducible.
5. Guard concurrent state transitions with transaction-safe patterns.

## Common Service Areas

| Service | Typical Data |
|---|---|
| `user-service` | users and profile/auth data |
| `event-service` | events and event metadata |
| `venue-service` | venues and venue metadata |
| `seat-service` | static seat maps |
| `seat-inventory-service` | per-event seat state and check-in logs |
| `ticket-service` | ticket ownership and QR metadata |
| `transfer-service` | transfer state transitions |
| `marketplace-service` | resale listings |
| `credit-transaction-service` | immutable credit ledger |

## Model and Migration Flow

```python
from app import db

class Resource(db.Model):
    __tablename__ = "resources"
    resourceId = db.Column(db.String(64), primary_key=True)
    createdAt = db.Column(db.DateTime, nullable=False)
```

Then:
- create migration
- review migration script for naming and nullability correctness
- run migration in Docker service container
- run seed script if service defines seeded shared IDs

## Must-Do Rules

1. Never move business-state orchestration logic into atomic storage services.
2. Keep write-side validation close to the service that owns the table.
3. Use deterministic status transitions for ticket, transfer, and marketplace domains.
4. Keep test fixtures aligned with Postman seeded IDs where possible.

## References

- [../../../services/README.md](../../../services/README.md)
- [../../../TESTING.md](../../../TESTING.md)
- [../../../INSTRUCTION.md](../../../INSTRUCTION.md)
- [../error-handling/SKILL.md](../error-handling/SKILL.md)
