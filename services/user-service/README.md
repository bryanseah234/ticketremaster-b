# user-service

`user-service` owns the user identity record for TicketRemaster.

## What it stores

- email
- hashed password and salt
- phone number
- role
- flag state
- optional `venueId` for staff users
- favorites and password reset tokens

## Design role

- this service owns identity persistence
- it does not issue JWTs; `auth-orchestrator` does that
- it accepts pre-hashed passwords from the orchestrator
- it exposes sensitive user lookup endpoints for internal callers only

## Current routes

- `GET /health`
- `GET /users`
- `POST /users`
- `GET /users/{userId}`
- `PATCH /users/{userId}`
- `GET /users/by-email/{email}`
- `GET /users/{userId}/favorites`
- `PUT /users/{userId}/favorites`
- `PATCH /admin/users/{userId}/flag`
- `GET /admin/users`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `POST /auth/verify-reset-token`
- `GET /admin/users/flagged`
- `PATCH /admin/users/{userId}/unflag`
- `GET /admin/users/{userId}`
- `GET /admin/users/search`

## Runtime notes

- dedicated PostgreSQL database
- migrations run at container startup in the Kubernetes flow
- read-heavy lookups are used by auth, marketplace, transfer, and admin dashboards

## Local verification

```powershell
python -m pytest -p no:cacheprovider services/user-service/tests
```

Related docs:

- [../README.md](../README.md)
- [../../TESTING.md](../../TESTING.md)
