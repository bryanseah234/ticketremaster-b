# otp-wrapper

`otp-wrapper` translates internal OTP requests into the external OutSystems notification contract.

## Design role

- sends OTP codes to phone numbers
- verifies OTP codes using provider-issued SIDs
- normalizes provider-specific behavior into the simple internal `{ "verified": true|false }` shape
- uses Redis-backed rate-limiting helpers to avoid brute-force abuse

## Current routes

- `GET /health`
- `POST /otp/send`
- `POST /otp/verify`

## Runtime notes

- no service-owned database
- depends on the external notification API URL and API key
- used by `auth-orchestrator` and `transfer-orchestrator`

## Local verification

```powershell
python -m pytest -p no:cacheprovider services/otp-wrapper/tests
```

Related docs:

- [../README.md](../README.md)
- [../../OUTSYSTEMS.md](../../OUTSYSTEMS.md)
