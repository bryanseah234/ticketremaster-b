# TicketRemaster Postman

Shared Postman assets for manual API and end-to-end testing live here.

Files:
- `TicketRemaster.postman_collection.json`: import this as the shared collection
- `TicketRemaster.local.postman_environment.json`: local Docker environment variables

Seed-data note for shared testing:
- The local environment is pre-aligned with seeded IDs:
  - `user_email=admin1@ticketremaster.local`
  - `venue_id=ven_001`
  - `event_id=evt_001`
- The collection also auto-captures and refreshes `user_id`, `venue_id`, `event_id`, and `inventory_id` from live responses so chained requests do not depend on empty placeholders.
- For stable team runs, apply migrations and run all service seed scripts before running the full collection.

Collection coverage:
- Health checks
- User, Venue, Seat, Event, Seat Inventory
- Ticket, Ticket Log, Marketplace, Transfer
- Credit Transaction
- Stripe Wrapper and OTP Wrapper
- RabbitMQ management endpoints
- OutSystems Credit Service external checks

Run from repo root:

```powershell
postman collection run .\postman\TicketRemaster.postman_collection.json -e .\postman\TicketRemaster.local.postman_environment.json --reporters cli
```

Related docs:
- End-to-end testing and troubleshooting: [../TESTING.md](../TESTING.md)
- Project documentation hub: [../README.md](../README.md)
- Stripe-specific test details: [../services/stripe-wrapper/README.md](../services/stripe-wrapper/README.md)
- OTP-specific test details: [../services/otp-wrapper/README.md](../services/otp-wrapper/README.md)

Suggested collection growth:
- `Health` for `GET /health` checks
- `Auth`, `Events`, `Purchase`, `Credits`, `Marketplace`, `Transfer`, `Tickets`, `Verify`
- Keep request examples aligned with the API reference and implementation as each phase lands
