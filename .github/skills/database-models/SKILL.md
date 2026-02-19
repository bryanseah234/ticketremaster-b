---
name: database-models
description: How to define SQLAlchemy models and database schemas for the four PostgreSQL databases in TicketRemaster. Covers naming conventions, UUID primary keys, timestamps, and init.sql patterns.
---

# Database Models & Schema Patterns

## When to Use

Use this skill when creating or modifying SQLAlchemy models, writing `init.sql` files, or working with any of the four databases: `seats_db`, `users_db`, `orders_db`, `events_db`.

## Architecture Rules

1. **One database per service.** No cross-DB joins. Ever.
2. **UUID primary keys.** Use `gen_random_uuid()` in Postgres or `uuid4()` in Python.
3. **Timestamps.** Every table must have `created_at` and `updated_at`.
4. **Enums as TEXT.** Store as `TEXT` with CHECK constraints, not Postgres ENUM type.
5. **init.sql runs on first boot** via Docker Compose volume mount.

## Database Ownership

| Database | Service | Tables |
|---|---|---|
| `seats_db` | Inventory Service | `seats`, `entry_logs` |
| `users_db` | User Service | `users` |
| `orders_db` | Order Service | `orders`, `transfers` |
| `events_db` | Event Service | `venues`, `events` |

## SQLAlchemy Model Pattern

```python
# Example: user-service/src/models/user.py
from sqlalchemy import Column, String, Numeric, Boolean, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True,
                     server_default=text("gen_random_uuid()"))
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    credit_balance = Column(Numeric(10, 2), nullable=False,
                           server_default=text("0.00"))
    is_flagged = Column(Boolean, nullable=False,
                       server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False,
                       server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                       server_default=text("NOW()"))
```

## init.sql Pattern

```sql
-- user-service/init.sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
    user_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(255) NOT NULL,
    phone         VARCHAR(20)  NOT NULL,
    credit_balance NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    is_flagged    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed data for development
INSERT INTO users (user_id, email, password_hash, full_name, phone, credit_balance)
VALUES
  ('f47ac10b-58cc-4372-a567-0e02b2c3d479', 'alice@example.com',
   '$2b$12$...', 'Alice Buyer', '+6591234567', 100.00),
  ('550e8400-e29b-41d4-a716-446655440000', 'bob@example.com',
   '$2b$12$...', 'Bob Seller', '+6598765432', 50.00)
ON CONFLICT (user_id) DO NOTHING;
```

## Session Management

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = (
    f"postgresql://{os.environ.get('DB_USER', 'postgres')}:"
    f"{os.environ['USER_DB_PASS']}@"
    f"{os.environ.get('DB_HOST', 'user-db')}:5432/"
    f"{os.environ.get('DB_NAME', 'users_db')}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

# Usage in routes
def get_user(user_id):
    with SessionLocal() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        return user
```

## Credit Operations (SELECT FOR UPDATE)

When modifying `credit_balance`, always use `SELECT FOR UPDATE` to prevent race conditions:

```python
with SessionLocal() as session:
    user = session.execute(
        text("SELECT * FROM users WHERE user_id = :uid FOR UPDATE"),
        {"uid": user_id}
    ).fetchone()

    if user.credit_balance < amount:
        session.rollback()
        raise InsufficientCreditsError()

    session.execute(
        text("UPDATE users SET credit_balance = credit_balance - :amt WHERE user_id = :uid"),
        {"amt": amount, "uid": user_id}
    )
    session.commit()
```

## Must-Do Rules

1. **Always use `FOR UPDATE`** when modifying balances or seat status
2. **Always wrap in transactions** — SQLAlchemy sessions auto-begin
3. **Use `pool_pre_ping=True`** to handle stale connections
4. **Never import models across services** — each service only knows its own DB
5. **Use `ON CONFLICT DO NOTHING`** in seed data to make init.sql idempotent

## References

- `INSTRUCTIONS.md` Section 3 — Full schema reference for all 4 databases
- `INSTRUCTIONS.md` Section 9 — Concurrency handling patterns
