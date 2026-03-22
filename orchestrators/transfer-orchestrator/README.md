# transfer-orchestrator

Transfer Orchestrator coordinates peer-to-peer ticket transfer including buyer/seller OTP, ownership movement, and compensation if any side-effect fails.

## Current Status

- Folder exists as a planned orchestrator module.
- Runtime implementation is not complete yet.
- Queue setup helper exists in this folder as an early utility.

## Planned Frontend-Facing Endpoints

- `POST /transfer/initiate`
- `POST /transfer/<transfer_id>/buyer-verify`
- `POST /transfer/<transfer_id>/seller-accept`
- `POST /transfer/<transfer_id>/seller-verify`
- `GET /transfer/<transfer_id>`
- `POST /transfer/<transfer_id>/cancel`

Source contract: [../../FRONTEND.md](../../FRONTEND.md).

## Downstream Dependencies

- `transfer-service` for workflow state persistence
- `ticket-service` for owner checks and updates
- `otp-wrapper` for buyer/seller verification
- OutSystems credit service for buyer-to-seller value transfer
- `credit-transaction-service` for immutable transfer ledger entries

## Flow Requirements

- enforce transfer ownership and duplicate-transfer prevention
- require both buyer and seller OTP verification before completion
- update credits and ownership in a compensation-safe sequence
- produce consistent status transitions in transfer records

## Related Docs

- Orchestrator index: [../README.md](../README.md)
- Transfer service contract: [../../services/transfer-service/README.md](../../services/transfer-service/README.md)
- OTP wrapper behavior: [../../services/otp-wrapper/README.md](../../services/otp-wrapper/README.md)
- Orchestrator implementation phases: [../../TASK.md](../../TASK.md)
- Saga and compensation pattern: [../../.github/skills/orchestrator-flow/SKILL.md](../../.github/skills/orchestrator-flow/SKILL.md)

