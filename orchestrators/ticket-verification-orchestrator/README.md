# ticket-verification-orchestrator

Ticket Verification Orchestrator handles staff-side scan validation by combining QR decryption, ownership validation, venue checks, and final check-in writes.

## Current Status

- Folder exists as a planned orchestrator module.
- Runtime implementation files are not built yet.
- Verification result rules are defined in planning docs and skills.

## Planned Frontend-Facing Endpoint

- `POST /verify/scan`

Source contract: [../../FRONTEND.md](../../FRONTEND.md).

## Downstream Dependencies

- `ticket-service` for ticket ownership and lifecycle state
- `ticket-log-service` for duplicate scan/audit checks
- `event-service` for venue/hall validation context
- `seat-inventory-service` for seat status/check-in mutation where applicable
- shared QR decryption logic and key configuration

## Verification Rules

- reject invalid or undecryptable payloads
- reject expired QR payloads
- reject hall mismatch
- reject duplicate scans
- on success, mark check-in and write log entry

## Related Docs

- Orchestrator index: [../README.md](../README.md)
- QR generation partner module: [../qr-orchestrator/README.md](../qr-orchestrator/README.md)
- Ticket log service: [../../services/ticket-log-service/README.md](../../services/ticket-log-service/README.md)
- Test flow references: [../../TESTING.md](../../TESTING.md)
- QR security and validation skill: [../../.github/skills/qr-encryption/SKILL.md](../../.github/skills/qr-encryption/SKILL.md)

