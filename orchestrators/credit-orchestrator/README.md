# Credit Orchestrator

The Credit Orchestrator serves as the centralized financial hub for the TicketRemaster platform. It coordinates credit balance inquiries, initiates Stripe top-ups, securely processes Stripe webhooks to finalize transactions, and maintains an immutable audit log of all credit movements.

## Role in the Architecture

- **Balance Source of Truth:** Routes all balance reads and writes to the external OutSystems `credit-service`.
- **Payment Processing:** Integrates with the `stripe-wrapper` to generate Payment Intents and validates cryptographic webhook signatures.
- **Idempotency Guard:** Prevents double-crediting during webhook retries or concurrent frontend confirmations by cross-referencing `paymentIntentId` against the `credit-transaction-service`.
- **Transaction Logging:** Ensures every successful top-up is recorded in the local transaction ledger.

## Exposed Endpoints

All endpoints are prefixed with `/credits` when routed through the API Gateway, but are registered natively in this service.

### `GET /credits/balance`
Retrieves the current authenticated user's credit balance from OutSystems.
- **Headers:** `Authorization: Bearer <JWT>`
- **Returns:** JSON object containing `creditBalance`.

### `POST /credits/topup/initiate`
Initiates a Stripe credit top-up.
- **Headers:** `Authorization: Bearer <JWT>`
- **Request Body:** `amount` (integer representing credits to purchase).
- **Process:** Calls `stripe-wrapper` to create a PaymentIntent.
- **Returns:** `clientSecret` and `paymentIntentId` used by the frontend Stripe SDK.

### `POST /credits/topup/confirm`
Frontend-driven confirmation endpoint to eagerly apply credits after a successful client-side Stripe flow.
- **Headers:** `Authorization: Bearer <JWT>`
- **Request Body:** `paymentIntentId`.
- **Process:**
  1. Retrieves PaymentIntent status from `stripe-wrapper`.
  2. **Idempotency Check:** Verifies if the transaction was already logged.
  3. Updates absolute balance in OutSystems.
  4. Logs transaction in `credit-transaction-service`.

### `POST /credits/topup/webhook`
Asynchronous Stripe webhook receiver. **(Unauthenticated)**
- **Headers:** `Stripe-Signature`
- **Process:**
  1. Forwards raw payload and signature to `stripe-wrapper` for cryptographic validation.
  2. Extracts `userId`, `credits`, and `paymentIntentId` upon success.
  3. **Idempotency Check:** Drops duplicate deliveries.
  4. Updates OutSystems balance and logs the transaction.
- **Local Testing:** Run `stripe listen --forward-to localhost:5011/stripe/webhook` (Note: ensure you route to the orchestrator port if testing through the API Gateway).

### `GET /credits/transactions`
Retrieves a paginated list of the user's past credit movements.
- **Headers:** `Authorization: Bearer <JWT>`
- **Query Params:** `page`, `limit`

## Downstream Dependencies

- **Stripe Wrapper (`STRIPE_WRAPPER_URL`):** Handles raw Stripe SDK interactions and signature validation.
- **Credit Transaction Service (`CREDIT_TRANSACTION_SERVICE_URL`):** Local PostgreSQL-backed service used for idempotency checks and ledger history.
- **OutSystems Credit Service (`CREDIT_SERVICE_URL`):** The external system of record for the actual `creditBalance`. Authenticated via `OUTSYSTEMS_API_KEY`.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET` | Secret key used to verify JWTs. | *Required* |
| `STRIPE_WRAPPER_URL` | Internal URL to the stripe-wrapper service. | `http://stripe-wrapper:5000` |
| `CREDIT_TRANSACTION_SERVICE_URL` | Internal URL to the credit-transaction-service. | `http://credit-transaction-service:5000` |
| `CREDIT_SERVICE_URL` | External URL to the OutSystems credit-service. | *Required* |
| `OUTSYSTEMS_API_KEY` | API Key for authenticating with OutSystems. | *Required* |

## Shared Components

This service imports the following shared modules (typically maintained centrally or copied from `auth-orchestrator`):
- `middleware.py`: Provides `@require_auth`.
- `service_client.py`: Provides `call_service()` and `call_credit_service()` (which auto-injects the OutSystems API key).

## Local Development & Testing

1. **Run the service:**
   ```bash
   docker compose up credit-orchestrator --build
   ```
2. **Swagger UI:** Available at `http://localhost:8102/apidocs` (or `http://localhost:8000/credits/apidocs` via Kong).
3. **Run Unit Tests:**
   ```bash
   docker compose run --rm credit-orchestrator pytest
   ```

## Error Handling
Returns standard platform error envelopes. Key errors include:
- `SERVICE_UNAVAILABLE` (503) if OutSystems or Stripe are unreachable.
- `VALIDATION_ERROR` (400) for missing amounts or IDs.
- `FORBIDDEN` (403) if a user attempts to confirm a payment intent belonging to another user.
