# TicketRemaster Postman Collections

This directory contains the shared Postman assets used for manual API testing and automated end-to-end integration workflows across the TicketRemaster microservices architecture.

## Files

- **`TicketRemaster.postman_collection.json`**: Legacy collection hitting atomic services directly on localhost ports. Used for Phase 0-5 internal service testing.
- **`TicketRemaster.local.postman_environment.json`**: Environment for the legacy collection (direct service ports).
- **`TicketRemaster.gateway.postman_collection.json`**: **Current** gateway collection. Tests all routes through Kong (auth, events, tickets, purchase, credits, marketplace, transfer, verify, admin, security checks).
- **`TicketRemaster.gateway-localhost.postman_environment.json`**: Gateway environment for `http://localhost:8000` (requires port-forward).
- **`TicketRemaster.gateway-public.postman_environment.json`**: Gateway environment for `https://ticketremasterapi.hong-yi.me`.

## How to Run

### Gateway tests (recommended)

```powershell
# Localhost (requires port-forward to be running)
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli

# Public URL
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli
```

Or use the startup script which runs both automatically:
```powershell
.\scripts\start_k8s.ps1
```

### Legacy atomic service tests

Requires Docker Compose running (not Minikube):
```powershell
newman run postman/TicketRemaster.postman_collection.json -e postman/TicketRemaster.local.postman_environment.json --reporters cli
```

## Related Documentation

- End-to-end testing and troubleshooting: [../TESTING.md](../TESTING.md)
- Stripe testing specifics: [../services/stripe-wrapper/README.md](../services/stripe-wrapper/README.md)
- OTP testing specifics: [../services/otp-wrapper/README.md](../services/otp-wrapper/README.md)
