# QR Orchestrator

The QR Orchestrator is responsible for providing users with a view of their owned tickets and generating dynamic, short-lived, encrypted QR codes required for secure venue entry.

## Role in the Architecture

- **Dynamic Encryption:** Generates a deterministic SHA-256 hash using a backend `QR_SECRET` alongside the `ticketId`, `userId`, `eventId`, `venueId`, and a generation timestamp. This prevents ticket counterfeiting and screenshotting.
- **State Synchronization:** Whenever a new QR code is requested, the orchestrator updates the underlying `ticket-service` with the fresh `qrHash` and `qrTimestamp`.
- **TTL Enforcement Design:** This service generates the hash and defines the 60-second TTL logic, but actual enforcement (rejecting expired hashes) is handled downstream by the `ticket-verification-orchestrator` during the physical scan.

## Exposed Endpoints

All endpoints are prefixed with `/tickets` when routed through the API Gateway, but are registered natively in this service.

### `GET /tickets`
Retrieves a list of all tickets owned by the currently authenticated user.
- **Headers:** `Authorization: Bearer <JWT>`
- **Process:**
  1. Fetches raw tickets from `ticket-service` by `ownerId`.
  2. Iterates over the tickets to fetch and inject full `event` and `venue` details from their respective services.
- **Returns:** An array of enriched ticket objects.

### `GET /tickets/<ticket_id>/qr`
Generates a fresh QR hash payload for a specific ticket, designed to be called right as the user displays their phone screen at the gate.
- **Headers:** `Authorization: Bearer <JWT>`
- **Process:**
  1. Validates the ticket exists and belongs to the authenticated `userId`.
  2. Validates the ticket status is exactly `"active"` (rejects `listed`, `used`, or `expired` tickets).
  3. Generates the SHA-256 hash string.
  4. Patches the `ticket-service` record with the new hash and timestamp.
  5. Enriches the response with `event` and `venue` details so the frontend can display contextual info alongside the QR graphic.
- **Returns:** The raw `qrHash`, `generatedAt`, `expiresAt` (calculated locally), and enriched event/venue metadata.

## Downstream Dependencies

- **Ticket Service (`TICKET_SERVICE_URL`):** Validates ownership, checks ticket status, and persists the generated `qrHash`.
- **Event Service (`EVENT_SERVICE_URL`):** Supplies event metadata for display.
- **Venue Service (`VENUE_SERVICE_URL`):** Supplies venue metadata for display.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET` | Secret key used to verify JWTs. | *Required* |
| `QR_SECRET` | **CRITICAL:** High-entropy secret used to salt the SHA-256 QR hash. Must match the secret used in `ticket-verification-orchestrator`. | *Required* |
| `QR_TTL_SECONDS` | Time-to-live for the QR code before a refresh is forced. | `60` |
| `TICKET_SERVICE_URL` | Internal URL to the atomic ticket-service. | `http://ticket-service:5000` |
| `EVENT_SERVICE_URL` | Internal URL to the atomic event-service. | `http://event-service:5000` |
| `VENUE_SERVICE_URL` | Internal URL to the atomic venue-service. | `http://venue-service:5000` |

## Shared Components

This service imports the following shared modules:
- `middleware.py`: Provides `@require_auth` to enforce ownership boundaries.
- `service_client.py`: Provides `call_service()` for robust internal HTTP requests.

## Local Development & Testing

1. **Run the service:**
   ```bash
   docker compose up qr-orchestrator --build
   ```
2. **Swagger UI:** Available at `http://localhost:8104/apidocs` (or `http://localhost:8000/tickets/apidocs` via Kong).
3. **Run Unit Tests:**
   ```bash
   docker compose run --rm qr-orchestrator pytest
   ```

## Error Handling
Returns standard platform error envelopes. Key errors include:
- `AUTH_FORBIDDEN` (403) if a user attempts to view or generate a QR for a ticket they do not own.
- `QR_INVALID` (400) if attempting to generate a QR for a ticket that is not `"active"`.
- `SERVICE_UNAVAILABLE` (503) if any downstream dependency is offline.
