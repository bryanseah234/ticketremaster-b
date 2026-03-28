# Marketplace Orchestrator

The Marketplace Orchestrator manages the public-facing ticket marketplace. It coordinates the creation of new listings, cancellation of active listings, and provides an aggregated read-model for browsing available tickets.

## Role in the Architecture

- **State Coordination:** Enforces synchronization between a ticket's status (`active` <-> `listed`) and its corresponding marketplace listing.
- **Saga Compensations:** During listing creation, if the `marketplace-service` fails to persist the listing, the orchestrator rolls back the `ticket-service` status to `active`.
- **Data Enrichment:** The public `/marketplace` route aggregates data from the `marketplace-service`, `ticket-service`, `event-service`, and `user-service` to deliver a complete payload suitable for frontend rendering.

## Exposed Endpoints

All endpoints are prefixed with `/marketplace` when routed through the API Gateway, but are registered natively in this service.

### `GET /marketplace`
Browses all active marketplace listings. **(Public, no JWT required)**
- **Query Params:** `eventId` (optional filter), `page`, `limit`
- **Process:**
  1. Fetches active listings from the `marketplace-service`.
  2. For each listing, fetches the associated ticket from `ticket-service`.
  3. Fetches the associated event details from `event-service`.
  4. Fetches the seller's profile from `user-service` to generate a masked `sellerName`.
- **Returns:** An array of enriched listings containing ticket, event, and seller data.

### `POST /marketplace/list`
Lists an owned ticket for sale on the marketplace.
- **Headers:** `Authorization: Bearer <JWT>`
- **Request Body:** `ticketId`, `price` (optional, defaults to original ticket price)
- **Process:**
  1. Validates the ticket exists and is owned by the authenticated user.
  2. Validates the ticket status is exactly `"active"`.
  3. Updates the ticket status to `"listed"` via `ticket-service`.
  4. Creates the listing record in `marketplace-service`.
  5. **Rollback:** If listing creation fails, reverts the ticket status to `"active"`.

### `DELETE /marketplace/<listing_id>`
Cancels an active listing and returns the ticket to the owner's usable inventory.
- **Headers:** `Authorization: Bearer <JWT>`
- **Process:**
  1. Validates the listing exists and the authenticated user is the seller.
  2. Validates the listing status is `"active"`.
  3. Updates the listing status to `"cancelled"` in `marketplace-service`.
  4. Reverts the associated ticket's status back to `"active"` in `ticket-service`.

## Downstream Dependencies

- **Marketplace Service (`MARKETPLACE_SERVICE_URL`):** Stores the listing state (`active`, `completed`, `cancelled`) and price.
- **Ticket Service (`TICKET_SERVICE_URL`):** Stores ticket ownership and status.
- **Event Service (`EVENT_SERVICE_URL`):** Provides event metadata for the public browse view.
- **User Service (`USER_SERVICE_URL`):** Provides seller identity details for the public browse view.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET` | Secret key used to verify JWTs. | *Required* |
| `MARKETPLACE_SERVICE_URL` | Internal URL to the atomic marketplace-service. | `http://marketplace-service:5000` |
| `TICKET_SERVICE_URL` | Internal URL to the atomic ticket-service. | `http://ticket-service:5000` |
| `EVENT_SERVICE_URL` | Internal URL to the atomic event-service. | `http://event-service:5000` |
| `USER_SERVICE_URL` | Internal URL to the atomic user-service. | `http://user-service:5000` |

## Shared Components

This service imports the following shared modules:
- `middleware.py`: Provides `@require_auth` for the `POST` and `DELETE` routes.
- `service_client.py`: Provides `call_service()` for robust, timeout-aware internal HTTP requests.

## Local Development & Testing

1. **Run the service:**
   ```bash
   docker compose up marketplace-orchestrator --build
   ```
2. **Swagger UI:** Available at `http://localhost:8105/apidocs` (or `http://localhost:8000/marketplace/apidocs` via Kong).
3. **Run Unit Tests:**
   ```bash
   docker compose run --rm marketplace-orchestrator pytest
   ```

## Error Handling
Returns standard platform error envelopes. Key errors include:
- `AUTH_FORBIDDEN` (403) if a user attempts to list/delist a ticket they do not own.
- `TICKET_NOT_FOUND` (400) if attempting to list a ticket that is already `listed`, `used`, or `expired`.
- `SERVICE_UNAVAILABLE` (503) if any downstream dependency is offline.
