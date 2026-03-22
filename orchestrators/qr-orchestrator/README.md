# qr-orchestrator

QR Orchestrator generates short-lived QR payloads for owned tickets and coordinates metadata updates needed for scan validation.

## Current Status

- Folder exists as a planned orchestrator module.
- Runtime implementation files are not built yet.
- Contract and encryption expectations are documented for future build.

## Planned Frontend-Facing Endpoints

- `GET /tickets`
- `GET /tickets/<ticket_id>/qr`

Source contract: [../../FRONTEND.md](../../FRONTEND.md).

## Downstream Dependencies

- `ticket-service` for ownership and ticket status checks
- `event-service` for venue/hall context
- `seat-inventory-service` (if ownership status is validated there)
- encryption key from environment (`QR_ENCRYPTION_KEY`)

## Behavioral Expectations

- QR payloads are generated on-demand, not persisted as image files.
- Each generated payload includes time metadata for short TTL enforcement.
- Old payloads become invalid through TTL and ownership checks.

## Implementation Notes

- Keep encryption/decryption logic centralized and deterministic.
- Align response shape with verification orchestrator input needs.
- Return clear error codes for expired, invalid, and unauthorized requests.

## Related Docs

- Orchestrator index: [../README.md](../README.md)
- Ticket verification contract: [../ticket-verification-orchestrator/README.md](../ticket-verification-orchestrator/README.md)
- Frontend API plan: [../../FRONTEND.md](../../FRONTEND.md)
- QR encryption reference: [../../.github/skills/qr-encryption/SKILL.md](../../.github/skills/qr-encryption/SKILL.md)

