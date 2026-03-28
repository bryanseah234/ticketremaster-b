# Auth Orchestrator

The Auth Orchestrator serves as the authentication entrypoint for the TicketRemaster platform. It handles user registration, login (credential verification), and the generation of stateless JWTs used by all other orchestrators.

It acts as a composition layer, offloading data persistence to the `user-service` and credit initialisation to the external `credit-service` (OutSystems).

## Role in the Architecture

- **Stateless:** Does not connect to a database. All state is maintained by downstream atomic services.
- **Security Boundary:** The only service that compares raw passwords against bcrypt hashes. Downstream services only store pre-hashed passwords.
- **Saga Pattern Initiator:** During registration, it orchestrates the creation of the user record and the initialization of their credit balance. If the credit initialization fails, it performs a compensating action to delete the newly created user.

## Exposed Endpoints

All endpoints are prefixed with `/auth` when routed through the API Gateway, but are registered on the root `/auth` within this service.

### `POST /auth/register`
Registers a new user account and initializes their credit balance.
- **Request Body:** `email`, `password`, `phoneNumber`, `role` (optional), `venueId` (optional, for staff).
- **Process:**
  1. Hashes the password using `bcrypt` and a unique salt.
  2. Calls `user-service` (`POST /users`) to create the identity record.
  3. Calls `credit-service` (`POST /credits`) to initialize a zero balance in OutSystems.
  4. **Rollback:** If `credit-service` fails, deletes the user from `user-service`.

### `POST /auth/login`
Authenticates a user and issues a JWT.
- **Request Body:** `email`, `password`.
- **Process:**
  1. Fetches user details (including salt and hash) from `user-service`.
  2. Verifies the provided password against the hash.
  3. Generates a JWT containing `userId`, `email`, `role`, and `venueId` (if role is staff).

### `GET /auth/me`
Retrieves the profile of the currently authenticated user.
- **Headers:** `Authorization: Bearer <JWT>`
- **Process:**
  1. Validates the JWT via shared middleware.
  2. Fetches full profile details from `user-service`.

### `GET /health`
Standard liveness probe endpoint returning HTTP 200 `{"status": "ok"}`.

## Downstream Dependencies

- **User Service (`USER_SERVICE_URL`):** Used for credential lookup, profile retrieval, and identity creation.
- **Credit Service (`CREDIT_SERVICE_URL`):** OutSystems endpoint used exclusively during registration to create a linked credit account.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET` | Secret key used to sign and verify JWTs. Must match across all orchestrators. | *Required* |
| `JWT_EXPIRY_HOURS` | Duration in hours before a token expires. | `24` |
| `USER_SERVICE_URL` | Internal URL to the atomic user-service. | `http://user-service:5000` |
| `CREDIT_SERVICE_URL` | External URL to the OutSystems credit-service. | *Required* |
| `OUTSYSTEMS_API_KEY` | API Key for authenticating with OutSystems. | *Required* |

## Shared Components (Reusable across Orchestrators)

This orchestrator defines two critical modules intended to be copied or shared across all other protected orchestrators:

1. **`middleware.py`:** Provides `@require_auth` and `@require_staff` decorators for JWT validation.
2. **`service_client.py`:** Provides `call_service()` and `call_credit_service()` for robust, timeout-aware internal HTTP requests.

## Local Development & Testing

1. **Run the service:**
   ```bash
   docker compose up auth-orchestrator --build
   ```
2. **Swagger UI:** Available at `http://localhost:8100/apidocs` (or `http://localhost:8000/auth/apidocs` via Kong) when running locally.
3. **Run Unit Tests:**
   ```bash
   docker compose run --rm auth-orchestrator pytest
   ```

## Error Handling
Returns consistent error envelopes conforming to the platform standard:
```json
{
  "error": {
    "code": "AUTH_INVALID_CREDENTIALS",
    "message": "Invalid email or password."
  }
}
```
Common codes include `VALIDATION_ERROR`, `EMAIL_ALREADY_EXISTS`, `AUTH_FORBIDDEN`, and `AUTH_TOKEN_EXPIRED`.
