# transfer-service

`transfer-service` stores the persistent record of a peer-to-peer ticket transfer.

## What it stores

- buyer and seller IDs
- listing link
- credit amount
- current transfer status
- OTP verification SIDs and flags
- completion and cancellation timestamps

## Current routes

- `GET /health`
- `POST /transfers`
- `GET /transfers`
- `GET /transfers/{transferId}`
- `PATCH /transfers/{transferId}`
- `POST /transfers/{transferId}/cancel`
- `GET /transfers/pending`

## Design role

- owns transfer persistence only
- does not call OTP, credits, or ticket services directly for the full workflow
- `transfer-orchestrator` is the layer that coordinates the saga around this record

## Local verification

```powershell
python -m pytest -p no:cacheprovider services/transfer-service/tests
```

Related docs:

- [../README.md](../README.md)
- [../../API.md](../../API.md)
