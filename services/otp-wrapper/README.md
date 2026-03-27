# otp-wrapper

OTP wrapper translates internal TicketRemaster OTP requests into the OutSystems Notification API contract.

## Endpoints

- `GET /health`
- `POST /otp/send`
- `POST /otp/verify`

## Request and Response Contract

### `POST /otp/send`

Internal request body:

```json
{
    "phoneNumber": "+6591234567"
}
```

Internal response body:

```json
{
    "sid": "VE..."
}
```

OutSystems call performed by wrapper:

- Method: `POST`
- URL: `<SMU_API_URL>/SendOTP`
- Payload:

```json
{
    "Mobile": "+6591234567"
}
```

### `POST /otp/verify`

Internal request body:

```json
{
    "sid": "VE...",
    "otp": "123456"
}
```

Internal response body:

```json
{
    "verified": true
}
```

OutSystems call performed by wrapper:

- Method: `POST`
- URL: `<SMU_API_URL>/VerifyOTP`
- Payload:

```json
{
    "VerificationSid": "VE...",
    "Code": "123456"
}
```

## Behavior Notes

- OutSystems Notification endpoints are POST-only.
- If opened in a browser (GET), the API returns:

```json
{ "Message": "The requested resource does not support http method 'GET'." }
```

- Wrapper validation failures return `400 VALIDATION_ERROR`.
- Upstream transport/API errors return `502 OTP_SEND_FAILED` or `502 OTP_VERIFY_FAILED`.
- For invalid OTP code responses that return upstream `400`, wrapper normalizes to `200 { "verified": false }`.

## Environment Variables

- `SMU_API_URL` example: `https://smuedu-dev.outsystemsenterprise.com/SMULab_Notification/rest/Notification`
- `SMU_API_KEY` used as outbound header `X-API-KEY`

## Automated Testing

Run wrapper unit tests:

```powershell
docker compose run --rm otp-wrapper python -m pytest -p no:cacheprovider tests
```

Tests cover:

- happy-path send and verify
- validation failures
- upstream failures
- upstream verify-400 normalization to `verified: false`

## Manual Testing

### 1) Through wrapper endpoint (recommended)

```powershell
curl -X POST "http://localhost:5012/otp/send" -H "Content-Type: application/json" -d "{\"phoneNumber\":\"+6591234567\"}"
```

Then verify:

```powershell
curl -X POST "http://localhost:5012/otp/verify" -H "Content-Type: application/json" -d "{\"sid\":\"<sid-from-send>\",\"otp\":\"123456\"}"
```

### 2) Direct upstream contract check (diagnostic)

```powershell
curl -X POST "https://smuedu-dev.outsystemsenterprise.com/SMULab_Notification/rest/Notification/SendOTP" -H "accept: application/json" -H "Content-Type: application/json" -d "{\"Mobile\":\"+6591234567\"}"
```

```powershell
curl -X POST "https://smuedu-dev.outsystemsenterprise.com/SMULab_Notification/rest/Notification/VerifyOTP" -H "accept: application/json" -H "Content-Type: application/json" -d "{\"VerificationSid\":\"<sid>\",\"Code\":\"123456\"}"
```

## Related Docs

- Full testing guide: [../../TESTING.md](../../TESTING.md)
- Postman usage and seeded variable assumptions: [../../postman/README.md](../../postman/README.md)
- Wrapper implementation source: [routes.py](routes.py)
