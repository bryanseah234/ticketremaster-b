# Ticket Purchase Orchestrator

The Ticket Purchase Orchestrator coordinates the end-to-end paid checkout flow. It manages high-concurrency seat holds via gRPC, enforces payment via external OutSystems credit checks, and executes a multi-step distributed saga to finalize ticket issuance.

## Role in the Architecture

- **High-Performance Locking:** Communicates directly with the `seat-inventory-service` over **gRPC** rather than REST to execute pessimistic row-level locks instantly.
- **Asynchronous Expiry (DLX):** On startup, this service bootstraps RabbitMQ queues and spawns a background thread running a Dead Letter Exchange (DLX) consumer. When a seat hold expires (TTL elapses), the queue automatically routes the message to the DLX consumer, which calls gRPC to release the seat back to the public pool.
- **Saga Pattern Execution:** The confirmation endpoint performs a multi-stage transaction:
  1. Validates hold status via gRPC.
  2. Verifies credit balance via OutSystems.
  3. Sells the seat via gRPC.
  4. Creates the ticket in `ticket-service`. (If this fails, it compensates by releasing the seat).
  5. Deducts credits in OutSystems.
  6. Logs the transaction in `credit-transaction-service`.

## Exposed Endpoints

All endpoints are prefixed with `/purchase` or `/tickets` when routed through the API Gateway.

### `GET /tickets`
Lists all tickets owned by the authenticated user, enriched with event details.
- **Headers:** `Authorization: Bearer <JWT>`
- **Process:** Fetches raw tickets from `ticket-service` and aggregates event names/dates from `event-service`.

### `POST /purchase/hold/<inventory_id>`
Holds a seat for purchase.
- **Headers:** `Authorization: Bearer <JWT>`
- **Process:**
  1. Calls `HoldSeat` via gRPC to `seat-inventory-service`.
  2. If successful, publishes a TTL message to the RabbitMQ `seat_hold_ttl_queue`.
- **Returns:** A `holdToken` and `heldUntil` timestamp.

### `DELETE /purchase/hold/<inventory_id>`
Manually releases a seat hold before the TTL expires.
- **Headers:** `Authorization: Bearer <JWT>`
- **Request Body:** `holdToken`
- **Process:** Calls `ReleaseSeat` via gRPC.

### `POST /purchase/confirm/<inventory_id>`
Confirms a purchase, deducts credits, and issues the ticket.
- **Headers:** `Authorization: Bearer <JWT>`
- **Request Body:** `eventId`, `holdToken`
- **Process:** Executes the Saga Pattern described above.
- **Returns:** The created `ticketId` and `status: active`.

## Background Processes

- **Queue Bootstrapper:** On startup, `startup_queue_setup.py` ensures the `seat_hold_ttl_queue` and `seat_hold_expired_queue` (DLX) are configured in RabbitMQ.
- **DLX Consumer Thread:** `dlx_consumer.py` runs continuously in the background, listening to the expired queue and issuing gRPC `ReleaseSeat` commands for orphaned holds.

## Downstream Dependencies

- **Seat Inventory Service (`SEAT_INVENTORY_GRPC_HOST` / `PORT`):** gRPC endpoint for locking and state transitions.
- **RabbitMQ (`RABBITMQ_HOST`):** Message broker for TTL routing.
- **OutSystems Credit Service:** External system of record for credit deductions.
- **Ticket Service (`TICKET_SERVICE_URL`):** For ticket creation.
- **Credit Transaction Service (`CREDIT_TRANSACTION_SERVICE_URL`):** For ledger logging.
- **Event Service (`EVENT_SERVICE_URL`):** For fetching ticket prices.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET` | Secret key used to verify JWTs. | *Required* |
| `SEAT_HOLD_DURATION_SECONDS` | Time in seconds before a hold expires. | `300` |
| `SEAT_INVENTORY_GRPC_HOST` | Hostname for the gRPC server. | `seat-inventory-service` |
| `SEAT_INVENTORY_GRPC_PORT` | Port for the gRPC server. | `50051` |
| `RABBITMQ_HOST` | RabbitMQ host. | `rabbitmq` |
| `OUTSYSTEMS_API_KEY` | API Key for OutSystems credit deductions. | *Required* |

## Local Development & Testing

1. **Run the service:**
   ```bash
   docker compose up ticket-purchase-orchestrator --build
   ```
2. **Swagger UI:** Available at `http://localhost:8103/apidocs` (or `http://localhost:8000/purchase/apidocs` via Kong).
3. **Testing Holds:** You can temporarily set `SEAT_HOLD_DURATION_SECONDS=10` in your `.env` to easily observe the RabbitMQ DLX consumer releasing seats automatically in the logs.

## Error Handling
Returns standard platform error envelopes. Key errors include:
- `SEAT_UNAVAILABLE` (409) if a seat is already held/sold.
- `PAYMENT_HOLD_EXPIRED` (410) if the user attempts to confirm a purchase after the TTL has passed.
- `INSUFFICIENT_CREDITS` (402) if the OutSystems balance check fails.
