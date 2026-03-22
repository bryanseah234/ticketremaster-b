# event-orchestrator

Event Orchestrator provides public, read-focused event browsing endpoints by aggregating data across event, venue, seat, and seat-inventory services.

## Current Status

- Folder exists as a planned orchestrator module.
- Runtime implementation files are not built yet.
- Intended to be one of the first orchestrators implemented because it is read-only and low-risk.

## Planned Frontend-Facing Endpoints

- `GET /events`
- `GET /events/<event_id>`
- `GET /events/<event_id>/seats`
- `GET /events/<event_id>/seats/<inventory_id>`

Source contract: [../../FRONTEND.md](../../FRONTEND.md).

## Downstream Dependencies

- `event-service`
- `venue-service`
- `seat-service`
- `seat-inventory-service` (REST side for inventory lookups)

## Aggregation Responsibilities

- merge event metadata with venue metadata
- combine static seat map with per-event seat inventory status
- return frontend-friendly payload shapes without exposing internal service boundaries

## Implementation Notes

- Keep this orchestrator public (no auth requirement for browse routes).
- Add bounded downstream timeouts and normalized failure codes.
- Reuse shared response format used in service docs and tests.

## Related Docs

- Orchestrator index: [../README.md](../README.md)
- Build order rationale: [../../INSTRUCTION.md](../../INSTRUCTION.md)
- Phase checklist: [../../TASK.md](../../TASK.md)
- Flask route patterns: [../../.github/skills/flask-service/SKILL.md](../../.github/skills/flask-service/SKILL.md)
- Error mapping patterns: [../../.github/skills/error-handling/SKILL.md](../../.github/skills/error-handling/SKILL.md)

