# auth-orchestrator

`auth-orchestrator` is the authentication entrypoint for the platform.

## Design role

- hashes passwords before persistence
- issues JWTs used by the other orchestrators
- coordinates registration with `user-service`, OutSystems credit initialization, and OTP send/verify
- manages token revocation through shared middleware helpers

## Current routes

- `POST /auth/register`
- `POST /auth/verify-registration`
- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/logout`
- `POST /auth/logout-all`

## Runtime notes

- stateless service, no owned database
- depends on `user-service`, `otp-wrapper`, Redis, and the external credit API
- registration is best-effort for external credit and OTP setup; the user record itself is created first

## Local verification

```powershell
python -m pytest -p no:cacheprovider orchestrators/auth-orchestrator/tests
```

Related docs:

- [../README.md](../README.md)
- [../../API.md](../../API.md)
