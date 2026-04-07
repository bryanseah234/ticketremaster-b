# transfer-orchestrator

`transfer-orchestrator` coordinates the full buyer-seller ticket transfer flow.

## Design role

- starts transfers from marketplace listings
- coordinates buyer and seller OTP verification
- re-checks credits immediately before the final saga step
- moves money and ownership through a compensation-aware workflow
- uses RabbitMQ for seller notification and transfer timeout scheduling

## Current routes

- `POST /transfer/initiate`
- `POST /transfer/{transferId}/buyer-verify`
- `POST /transfer/{transferId}/seller-accept`
- `POST /transfer/{transferId}/seller-reject`
- `POST /transfer/{transferId}/seller-verify`
- `GET /transfer/pending`
- `GET /transfer/{transferId}`
- `POST /transfer/{transferId}/resend-otp`
- `POST /transfer/{transferId}/cancel`

## Runtime notes

- stateless service, no owned database
- depends on `marketplace-service`, `transfer-service`, `otp-wrapper`, `credit-transaction-service`, `ticket-service`, `user-service`, RabbitMQ, and OutSystems

## Local verification

```powershell
python -m pytest -p no:cacheprovider orchestrators/transfer-orchestrator/tests
```

Related docs:

- [../README.md](../README.md)
- [../../API.md](../../API.md)
