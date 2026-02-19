# Contributing to TicketRemaster Backend

> Guidelines for the IS213 project team.

---

## Getting Started

1. Clone the repo:

   ```bash
   git clone <repo-url>
   cd ticketremaster-b
   ```

2. Copy environment variables:

   ```bash
   cp .env.example .env
   # Fill in actual values
   ```

3. Start all services:

   ```bash
   docker compose up --build
   ```

4. For hot-reload during development:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
   ```

---

## Git Branching Strategy

We use **GitHub Flow** — simple and effective for a team project.

| Branch | Purpose |
|---|---|
| `main` | Production-ready code. Always deployable. |
| `feature/<name>` | New feature development. Branch from `main`. |
| `fix/<name>` | Bug fixes. Branch from `main`. |
| `docs/<name>` | Documentation-only changes. |

### Workflow

1. Create a branch from `main`:

   ```bash
   git checkout -b feature/purchase-flow
   ```

2. Make commits with clear messages:

   ```
   feat: implement seat reservation with NOWAIT locking
   fix: handle expired hold in payment endpoint
   docs: add QR refresh endpoint to API.md
   ```

3. Push and open a Pull Request on GitHub.

4. CI runs linting and tests automatically on PR.

5. Get at least 1 team member review before merging.

6. Squash-merge into `main`.

---

## Commit Message Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Usage |
|---|---|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation changes |
| `refactor:` | Code restructuring (no behaviour change) |
| `test:` | Adding or updating tests |
| `chore:` | Build, CI, dependency updates |

---

## Code Conventions

### Python

- **Formatter:** Use `black` (line length 88)
- **Linter:** Use `flake8`
- **Imports:** Use `isort` for sorting
- **Type hints:** Encouraged but not enforced for this project
- **Docstrings:** Required for public functions and classes

### Project Structure

Each microservice follows the same layout:

```
<service-name>/
├── init.sql           # DB schema + seed data
├── requirements.txt   # Python dependencies
├── Dockerfile
└── src/
    ├── app.py         # Flask app entry point
    ├── models/        # SQLAlchemy / data models
    └── services/      # Business logic
```

---

## Pull Request Checklist

Before requesting review:

- [ ] Code runs locally (`docker compose up --build`)
- [ ] No linting errors (`flake8`)
- [ ] No formatting issues (`black --check`)
- [ ] Added/updated Flasgger docstrings for new/changed endpoints
- [ ] Tested new endpoints manually (curl / Postman / Swagger UI)
- [ ] Updated relevant `.md` docs if behaviour changed

---

---

## Useful Commands

```bash
# Start everything
docker compose up --build

# Start with dev hot-reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Rebuild a single service
docker compose up --build user-service

# View logs for a service
docker compose logs -f orchestrator-service

# Clean slate (deletes all data)
docker compose down -v && docker compose up --build

# Run linting locally
pip install flake8 black isort
flake8 .
black --check .
isort --check .

# Access RabbitMQ management UI
# http://localhost:15672 (guest/guest)

# Access Swagger UI (per service)
# http://localhost:5003/apidocs/  (Orchestrator)
```
