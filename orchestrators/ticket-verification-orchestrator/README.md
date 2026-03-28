# Ticket Verification Orchestrator

The Ticket Verification Orchestrator is a staff-facing service designed to process physical entry into venues. It validates dynamic QR codes, executes comprehensive security and state checks, prevents duplicate entries, and mutates the final ticket state upon successful check-in.

## Role in the Architecture

- **Staff Authorization Boundary:** This orchestrator strictly requires a `staff` or `admin` role JWT. It securely reads the staff member's assigned `venueId` directly from the JWT to prevent spoofing via request bodies.
- **Strict Validation Pipeline:** Executes an immutable sequence of business rules to ensure a ticket is fully valid for the specific venue at the specific time.
- **Audit Logging:** Regardless of the verification outcome (success, expired, wrong venue, duplicate), it logs the scan attempt to the `ticket-log-service` for security auditing and dispute resolution.

## The Verification Pipeline

When a QR code is scanned, the orchestrator enforces the following checks in exact order:
1. **Hash Lookup:** Finds the ticket associated with the scanned `qrHash`.
2. **TTL Enforcement:** Validates the `qrTimestamp` is less than `QR_TTL_SECONDS` (60s) old. Rejects as `QR_EXPIRED` if stale.
3. **Event Validation:** Confirms the parent event still exists and is active.
4. **Seat State:** Confirms the associated seat is definitively marked as `sold` in the `seat-inventory-service`.
5. **Ticket State:** Confirms the ticket status is `active` (rejecting `listed`, `used`, or `pending_transfer`).
6. **Duplicate Check:** Queries the `ticket-log-service` to ensure no prior `checked_in` log exists for this ticket.
7. **Venue Match:** Compares the ticket's `venueId` against the staff member's JWT `venueId`. If mismatched, returns a `WRONG_HALL` error detailing the correct venue.
8. **Finalization:** If all checks pass, updates the ticket status to `used` and writes a `checked_in` log.

## Exposed Endpoints

All endpoints are prefixed with `/verify` when routed through the API Gateway, but are registered natively in this service.

### `POST /verify/scan`
The primary entrypoint for staff scanning a physical or digital QR code.
- **Headers:** `Authorization: Bearer <JWT>`
- **Request Body:** `qrHash`
- **Returns:** A `200 OK` with enriched event/seat details on success, or a `400`/`404`/`409` with specific error codes (e.g., `QR_EXPIRED`, `ALREADY_CHECKED_IN`, `WRONG_HALL`).

### `POST /verify/manual`
A fallback endpoint allowing staff to manually verify and check-in a ticket by its raw ID (e.g., if the user's phone screen is broken).
- **Headers:** `Authorization: Bearer <JWT>`
- **Request Body:** `ticketId`
- **Process:** Bypasses the QR hash lookup and TTL check, but enforces all other pipeline rules (Event, Seat, Ticket State, Duplicates, and Venue Match).

## Downstream Dependencies

- **Ticket Service (`TICKET_SERVICE_URL`):** Looks up the QR hash and mutates the ticket status to `used`.
- **Ticket Log Service (`TICKET_LOG_SERVICE_URL`):** Reads history to prevent duplicate scans; writes the final outcome of every scan attempt.
- **Event Service (`EVENT_SERVICE_URL`):** Validates the event context.
- **Venue Service (`VENUE_SERVICE_URL`):** Fetches the "correct" venue details to display to the user if they are at the wrong hall.
- **Seat Inventory Service (`SEAT_INVENTORY_SERVICE_URL`):** Validates the seat was not refunded or released.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET` | Secret key used to verify JWTs. | *Required* |
| `QR_TTL_SECONDS` | Time-to-live for the QR code before a refresh is forced. Must align with `qr-orchestrator`. | `60` |
| `TICKET_SERVICE_URL` | Internal URL to the atomic ticket-service. | `http://ticket-service:5000` |
| `TICKET_LOG_SERVICE_URL` | Internal URL to the atomic ticket-log-service. | `http://ticket-log-service:5000` |
| `EVENT_SERVICE_URL` | Internal URL to the atomic event-service. | `http://event-service:5000` |
| `VENUE_SERVICE_URL` | Internal URL to the atomic venue-service. | `http://venue-service:5000` |
| `SEAT_INVENTORY_SERVICE_URL` | Internal URL to the atomic seat-inventory-service. | `http://seat-inventory-service:5000` |

## Shared Components

This service imports the following shared modules:
- `middleware.py`: Provides the strict `@require_staff` decorator.
- `service_client.py`: Provides `call_service()` for robust internal HTTP requests.

## Local Development & Testing

1. **Run the service:**
   ```bash
   docker compose up ticket-verification-orchestrator --build
   ```
2. **Swagger UI:** Available at `http://localhost:8108/apidocs` (or `http://localhost:8000/verify/apidocs` via Kong).
3. **Run Unit Tests:**
   ```bash
   docker compose run --rm ticket-verification-orchestrator pytest
   ```
