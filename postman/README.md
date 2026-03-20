# TicketRemaster Postman

Shared Postman assets for manual API and end-to-end testing live here.

Files:
- `TicketRemaster.postman_collection.json`: import this as the shared collection
- `TicketRemaster.local.postman_environment.json`: local Docker environment variables

Suggested collection growth:
- `Health` for `GET /health` checks
- `Auth`, `Events`, `Purchase`, `Credits`, `Marketplace`, `Transfer`, `Tickets`, `Verify`
- Keep request examples aligned with the API reference and implementation as each phase lands
