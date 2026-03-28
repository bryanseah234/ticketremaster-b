# Event Orchestrator

The Event Orchestrator provides public, read-focused event browsing endpoints by aggregating data across multiple atomic services. It acts as the frontend's unified gateway for browsing events, venues, and live seat maps without exposing the underlying database boundaries.

## Role in the Architecture

- **Public Access:** Most endpoints are public and do not require JWT authentication, serving as the entry point for the public-facing storefront.
- **Data Aggregation (Scatter-Gather):** Merges event metadata with venue location data and physical seat mappings with real-time seat inventory statuses.
- **Admin Automation:** Exposes a `POST /admin/events` route that simplifies event creation by automatically scaffolding the seat inventory (based on the venue's physical seats) in a single API call.

## Exposed Endpoints

All endpoints are prefixed with `/events` or `/venues` when routed through the API Gateway, but are registered natively in this service.

### `GET /venues`
Retrieves a list of all active venues.
- **Process:** Acts as a direct proxy to the `venue-service`.

### `GET /events`
Lists all events, enriched with basic venue details and a count of available seats.
- **Query Params:** `type` (optional filter), `page`, `limit`
- **Process:** 
  1. Fetches events from `event-service`.
  2. For each event, fetches venue details from `venue-service`.
  3. Fetches seat inventory from `seat-inventory-service` and counts seats with status `"available"`.

### `GET /events/<event_id>`
Retrieves comprehensive details for a single event.
- **Process:** Fetches the event record and enriches it with the full venue object.

### `GET /events/<event_id>/seats`
Retrieves the complete seat map for a specific event, combining physical seat layout with real-time availability.
- **Process:**
  1. Fetches the event to identify the `venueId`.
  2. Fetches the real-time inventory list from `seat-inventory-service`.
  3. Fetches the physical layout (rows, numbers) from `seat-service`.
  4. Merges the two datasets to return an array of seats containing both coordinates (`rowNumber`, `seatNumber`) and state (`status`, `heldUntil`).

### `GET /events/<event_id>/seats/<inventory_id>`
Retrieves granular details for a specific seat, enriched with parent event and venue data.

### `POST /admin/events`
Creates a new event and automatically provisions its entire seat inventory.
- **Process:**
  1. Validates the `venueId` exists in `venue-service`.
  2. Creates the event in `event-service`.
  3. Fetches all physical seats for the venue from `seat-service`.
  4. Issues a batch `POST` to `seat-inventory-service` to generate an `"available"` inventory record for every physical seat.

## Downstream Dependencies

- **Event Service (`EVENT_SERVICE_URL`):** Core metadata for events.
- **Venue Service (`VENUE_SERVICE_URL`):** Metadata for venues (address, capacity).
- **Seat Service (`SEAT_SERVICE_URL`):** Physical layout of venues (rows, seat numbers).
- **Seat Inventory Service (`SEAT_INVENTORY_SERVICE_URL`):** Real-time, transactional state of seats (`available`, `held`, `sold`).

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EVENT_SERVICE_URL` | Internal URL to the atomic event-service. | `http://event-service:5000` |
| `VENUE_SERVICE_URL` | Internal URL to the atomic venue-service. | `http://venue-service:5000` |
| `SEAT_SERVICE_URL` | Internal URL to the atomic seat-service. | `http://seat-service:5000` |
| `SEAT_INVENTORY_SERVICE_URL` | Internal URL to the atomic seat-inventory-service. | `http://seat-inventory-service:5000` |

## Shared Components

This service imports the `service_client.py` module to execute robust, timeout-aware internal HTTP requests. It deliberately omits JWT `middleware.py` as it is fundamentally a public aggregator.

## Local Development & Testing

1. **Run the service:**
   ```bash
   docker compose up event-orchestrator --build
   ```
2. **Swagger UI:** Available at `http://localhost:8101/apidocs` (or `http://localhost:8000/events/apidocs` via Kong).
3. **Run Unit Tests:**
   ```bash
   docker compose run --rm event-orchestrator pytest
   ```

## Error Handling
Returns standard platform error envelopes. Key errors include:
- `SERVICE_UNAVAILABLE` (503) if any downstream dependency is offline.
- `EVENT_NOT_FOUND` / `VENUE_NOT_FOUND` (404) if requested resources do not exist.
- `VALIDATION_ERROR` (400) for missing fields during admin event creation.
