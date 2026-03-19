# user-service

Stores user accounts and exposes create, read, list, and partial update endpoints for registration and lookup.

## Database modes
- Main runtime and manual testing mode: PostgreSQL in Docker via `user-service-db`
- Automated local test mode: in-memory SQLite used only by the pytest suite

The service no longer falls back to a local SQLite file at runtime. You must provide `USER_SERVICE_DATABASE_URL` (or `DATABASE_URL`) for manual runs.

## Structure
- `app.py`: creates the Flask app, loads configuration, initializes SQLAlchemy and Flask-Migrate, and exposes `GET /health`
- `models.py`: defines the `User` SQLAlchemy model and the response serialization helper
- `routes.py`: contains the HTTP endpoints for listing users, creating users, fetching users, and patching users
- `seed.py`: inserts two default admin users for shared team testing in an idempotent way
- `requirements.txt`: Python dependencies needed to run the service and local automated tests
- `Dockerfile`: container build instructions for running the service in Docker
- `README.md`: service-level notes and a quick explanation of the file layout

## Folders
- `migrations/`: Alembic and Flask-Migrate files used to create and evolve the database schema
- `migrations/versions/`: versioned migration scripts, including the initial `users` table migration
- `tests/`: local automated pytest checks for service logic; these are separate from Docker/Postman manual testing

## Seed data
Running `seed.py` creates these two admin users if they do not already exist:
- `admin1@ticketremaster.local`
- `admin2@ticketremaster.local`

## Route behavior
- `GET /users`: returns non-sensitive user summaries
- `POST /users`: creates a new user from pre-hashed credentials
- `GET /users/<user_id>`: returns the full stored user record
- `PATCH /users/<user_id>`: partially updates allowed user fields
- `GET /users/by-email/<email>`: returns the full stored user record by email

## Testing
### Automated local tests
These tests are only for local automated verification. They do not run in Docker and they do not use the Docker Postgres database.

Run them from the repo root:

```powershell
python -m pytest -p no:cacheprovider services/user-service/tests
```

### Docker and Postman manual testing
This is the main manual testing path for the service.

Make sure `USER_SERVICE_DATABASE_URL` is not set to a local SQLite value in your shell before running Docker commands.

Start the PostgreSQL container:

```powershell
docker compose up -d user-service-db
```

Apply the migration in Docker:

```powershell
docker compose run --rm user-service python -m flask --app app.py db upgrade -d migrations
```

Seed the two admin users in Docker:

```powershell
docker compose run --rm user-service python seed.py
```

Start the user-service container:

```powershell
docker compose up --build -d user-service
```

Optional log check:

```powershell
docker compose logs -f user-service user-service-db
```

Base URL for Postman:

```text
http://127.0.0.1:5000
```

### Postman test flow
Test the endpoints in this order:
1. `GET /health`
2. `GET /users`
3. `GET /users/by-email/admin1@ticketremaster.local`
4. `GET /users/<user_id>`
5. `PATCH /users/<user_id>`
6. `POST /users`

Example request body for `POST /users`:

```json
{
  "email": "jane@example.com",
  "password": "hashed-password",
  "salt": "salt-value",
  "phoneNumber": "+6591234567"
}
```

Example request body for `PATCH /users/<user_id>`:

```json
{
  "phoneNumber": "+6588888888",
  "isFlagged": true
}
```

Useful Postman flow:
- after `GET /users`, copy an admin `userId` for direct lookup and patch testing
- confirm `GET /users` does not expose `password` or `salt`
- confirm `GET /users/<user_id>` and `GET /users/by-email/<email>` do expose the full stored record
- use `POST /users` to create additional non-admin test users as needed

### Restarting later
Once you have already:
- run the migration
- seeded the admin users
- kept the Docker volume

then normal restarts usually only need:

```powershell
docker compose up
```

or in detached mode:

```powershell
docker compose up -d
```

This works because `docker compose down` removes containers but keeps the named PostgreSQL volume, so your database data is still there the next time the stack starts.

You only need to rerun migration or seeding if:
- you used `docker compose down -v`
- you added a new migration
- you want to recreate the initial admin users in a reset database

## Docker cleanup
Stop the user-service containers but keep the database data volume:

```powershell
docker compose stop user-service user-service-db
```

Stop and remove the user-service containers but keep the database volume:

```powershell
docker compose rm -fsv user-service user-service-db
```

Bring the whole compose stack down:

```powershell
docker compose down
```

Bring the stack down and also delete the PostgreSQL volume for a full reset:

```powershell
docker compose down -v
```

