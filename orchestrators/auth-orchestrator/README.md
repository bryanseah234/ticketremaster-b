# auth-orchestrator

Auth Orchestrator is the authentication entrypoint for login/token flows and user identity claims used by other orchestrators.

## Current Status

- Folder exists as a planned orchestrator module.
- Runtime implementation files are not built yet.
- This README defines the intended contract and dependencies.

## Planned Frontend-Facing Endpoints

- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/refresh` (optional if refresh tokens are introduced)

The exact baseline in this repo is documented in [../../FRONTEND.md](../../FRONTEND.md).

## Downstream Dependencies

- `user-service` for credential lookup and user profile checks
- `credit-service` (OutSystems) only if balance/context is included in auth response
- shared JWT config from environment (`JWT_SECRET`, expiry settings)

## Implementation Notes

- Keep this orchestrator stateless.
- Issue JWT with consistent claim names (`userId`, `email`, `role`, optional `venueId`).
- Reuse one middleware pattern across all protected orchestrators.
- Return consistent error envelope aligned with [../../TESTING.md](../../TESTING.md) expectations.

## Suggested Folder Layout

- `app.py`
- `routes.py`
- `middleware.py`
- `requirements.txt`
- `Dockerfile`

## Related Docs

- Orchestrator index: [../README.md](../README.md)
- Global implementation guide: [../../INSTRUCTION.md](../../INSTRUCTION.md)
- Task checklist: [../../TASK.md](../../TASK.md)
- Error patterns: [../../.github/skills/error-handling/SKILL.md](../../.github/skills/error-handling/SKILL.md)
- Flask endpoint patterns: [../../.github/skills/flask-service/SKILL.md](../../.github/skills/flask-service/SKILL.md)

