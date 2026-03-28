# TicketRemaster Postman Collections

This directory contains the shared Postman assets used for manual API testing and automated end-to-end integration workflows across the TicketRemaster microservices architecture.

## Files

- **`TicketRemaster.postman_collection.json`**: The core collection file. It contains grouped requests covering health checks, atomic service operations, external wrappers, and RabbitMQ verifications.
- **`TicketRemaster.local.postman_environment.json`**: The local environment file. It maps variables to your `localhost` Docker ports and stores dynamic state.

## Core Features & Automation

To reduce manual copy-pasting during end-to-end flows, this collection heavily utilizes **Postman Test Scripts** to auto-capture IDs from responses and set them as environment variables. 

When you run a sequence of requests, downstream requests automatically inherit the correct context. For example:
- Creating a user auto-sets `{{user_id}}`.
- Listing venues auto-sets `{{venue_id}}`.
- Creating a ticket auto-sets `{{ticket_id}}` and `{{ticket_qr_hash}}`.

### Seed Data Assumptions
The local environment assumes baseline seed data has been applied to the database. It defaults to:
- `user_email` = `admin1@ticketremaster.local`
- `venue_id` = `ven_001`
- `event_id` = `evt_001`

**Important:** For stable test runs, ensure you have run all migrations and seed scripts (e.g., via `bash scripts/start_and_seed.sh`) before executing the collection.

## Collection Coverage

The collection is currently structured to validate **Phase 0 through Phase 5** of the project implementation:

1. **Health Checks:** Validates the `GET /health` endpoint across all 12 backend services.
2. **Atomic Services:** Full CRUD validation for User, Venue, Seat, Event, Seat Inventory, Ticket, Ticket Log, Marketplace, Transfer, and Credit Transaction services.
3. **External Wrappers:** Validates Stripe intent creation/webhook signatures and SMU OTP dispatch/verification.
4. **RabbitMQ Checks:** Hits the RabbitMQ Management API to verify the existence of the `seat_hold_ttl_queue`, `seat_hold_expired_queue`, and `seller_notification_queue`.
5. **OutSystems Checks:** Validates the external `credit-service` contract (Creation, Reads, and Updates) using the injected `{{outsystems_api_key}}`.

## How to Run Locally

You can run the entire collection headlessly via the Postman CLI directly from the repository root:

```powershell
# Install Postman CLI if you haven't already: npm install -g newman
postman collection run .\postman\TicketRemaster.postman_collection.json -e .\postman\TicketRemaster.local.postman_environment.json --reporters cli
```

Alternatively, import both JSON files into the Postman Desktop App to run requests individually and inspect payloads.

## Future Expansion (Phase 6+)

As the API Gateway (Kong) and Orchestrators are finalized, this collection should be expanded to include higher-level business journeys. Suggested future folders:
- `Auth`: `/auth/register`, `/auth/login`, `/auth/me`
- `Events`: `/events`, `/events/<id>/seats`
- `Purchase`: `/purchase/hold`, `/purchase/confirm`
- `Credits`: `/credits/balance`, `/credits/topup/initiate`
- `Marketplace`: `/marketplace/list`, `DELETE /marketplace/<id>`
- `Transfer`: P2P OTP Saga flow
- `Verify`: Staff QR scanning flow

## Related Documentation

- End-to-end testing and troubleshooting: [../TESTING.md](../TESTING.md)
- Stripe testing specifics: [../services/stripe-wrapper/README.md](../services/stripe-wrapper/README.md)
- OTP testing specifics: [../services/otp-wrapper/README.md](../services/otp-wrapper/README.md)
