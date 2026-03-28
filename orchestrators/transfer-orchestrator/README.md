# Transfer Orchestrator

The Transfer Orchestrator manages the complex, multi-party peer-to-peer (P2P) ticket transfer flow. It ensures secure ownership exchanges by enforcing two-factor authentication (OTP) for both buyers and sellers, and executes a distributed saga to safely move credits and ticket ownership.

## Role in the Architecture

- **Multi-Party Workflow:** Coordinates state transitions between a buyer and a seller across multiple asynchronous steps.
- **OTP Integration:** Wraps external SMU Notification API calls via the `otp-wrapper` to send and verify SMS tokens for both parties.
- **Asynchronous Notification:** Uses RabbitMQ (`seller_notification_queue`) to decouple the buyer's request from the seller's notification logic.
- **Saga Pattern & Compensation:** Upon final seller verification, it executes a strict sequence:
  1. Deduct buyer credits (OutSystems)
  2. Credit seller (OutSystems)
  3. Log buyer transaction
  4. Log seller transaction
  5. Transfer ticket ownership
  6. Complete marketplace listing
  7. Complete transfer record
  *If any step fails, it compensates by restoring OutSystems balances and marking the transfer as `failed`.*

## Exposed Endpoints

All endpoints are prefixed with `/transfer` when routed through the API Gateway, but are registered natively in this service.

### `POST /transfer/initiate`
**Buyer** initiates the purchase of a listed ticket.
- **Headers:** `Authorization: Bearer <JWT>`
- **Request Body:** `listingId`
- **Process:** Validates buyer has sufficient OutSystems credits, creates the transfer record (`pending_seller_acceptance`), and publishes a RabbitMQ notification to the seller.

### `POST /transfer/<transfer_id>/seller-accept`
**Seller** accepts the incoming request.
- **Headers:** `Authorization: Bearer <JWT>`
- **Process:** Triggers an OTP SMS to the **buyer** via `otp-wrapper`. State moves to `pending_buyer_otp`.

### `POST /transfer/<transfer_id>/buyer-verify`
**Buyer** submits the OTP sent to their phone.
- **Headers:** `Authorization: Bearer <JWT>`
- **Request Body:** `otp`
- **Process:** Verifies the OTP. If valid, triggers an OTP SMS to the **seller**. State moves to `pending_seller_otp`.

### `POST /transfer/<transfer_id>/seller-verify`
**Seller** submits the final OTP, completing the transaction.
- **Headers:** `Authorization: Bearer <JWT>`
- **Request Body:** `otp`
- **Process:** Verifies the OTP, does a final real-time check of the buyer's credit balance, and executes the Saga to swap credits and ticket ownership.

### Additional Lifecycle Endpoints
- **`GET /transfer/pending`:** Lists all transfers awaiting the authenticated seller's acceptance.
- **`GET /transfer/<transfer_id>`:** Polls transfer status (accessible only by the involved buyer/seller).
- **`POST /transfer/<transfer_id>/seller-reject`:** Seller actively rejects the request; reverts listing and ticket to active.
- **`POST /transfer/<transfer_id>/resend-otp`:** Resends the OTP to whoever's turn it is to verify.
- **`POST /transfer/<transfer_id>/cancel`:** Cancels an in-progress transfer (if not yet completed/failed).

## Background Processes

- **Queue Bootstrapper:** On startup, `startup_queue_setup.py` ensures the `seller_notification_queue` is configured in RabbitMQ.
- **Seller Consumer Thread:** `seller_consumer.py` runs continuously in the background, listening for new transfer initiations to trigger push notifications or emails to the seller.

## Downstream Dependencies

- **Marketplace Service (`MARKETPLACE_SERVICE_URL`):** Validates and mutates listing states.
- **Transfer Service (`TRANSFER_SERVICE_URL`):** Persists the state machine of the transfer.
- **OTP Wrapper (`OTP_WRAPPER_URL`):** Sends and verifies SMS codes.
- **Ticket Service (`TICKET_SERVICE_URL`):** Transfers ownership (`ownerId`).
- **User Service (`USER_SERVICE_URL`):** Fetches phone numbers for OTP dispatch.
- **Credit Transaction Service (`CREDIT_TRANSACTION_SERVICE_URL`):** Logs the financial movements.
- **OutSystems Credit Service:** Deducts and credits balances.
- **RabbitMQ (`RABBITMQ_HOST`):** Broker for seller notifications.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET` | Secret key used to verify JWTs. | *Required* |
| `RABBITMQ_HOST` | RabbitMQ host. | `rabbitmq` |
| `OUTSYSTEMS_API_KEY` | API Key for OutSystems credit updates. | *Required* |
| `MARKETPLACE_SERVICE_URL` | Internal URL to marketplace-service. | `http://marketplace-service:5000` |
| `TRANSFER_SERVICE_URL` | Internal URL to transfer-service. | `http://transfer-service:5000` |
| `OTP_WRAPPER_URL` | Internal URL to otp-wrapper. | `http://otp-wrapper:5000` |

## Local Development & Testing

1. **Run the service:**
   ```bash
   docker compose up transfer-orchestrator --build
   ```
2. **Swagger UI:** Available at `http://localhost:8107/apidocs` (or `http://localhost:8000/transfer/apidocs` via Kong).
3. **Run Unit Tests:**
   ```bash
   docker compose run --rm transfer-orchestrator pytest
   ```
