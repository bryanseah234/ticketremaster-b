# TicketRemaster Postman Assets

This folder contains the maintained API collections used for gateway smoke testing and older direct-service diagnostics.

## Current assets

- `TicketRemaster.gateway.postman_collection.json`: maintained gateway smoke suite
- `TicketRemaster.gateway-localhost.postman_environment.json`: `http://localhost:8000`
- `TicketRemaster.gateway-public.postman_environment.json`: `https://ticketremasterapi.hong-yi.me`
- `TicketRemaster.postman_collection.json`: legacy direct-service collection
- `TicketRemaster.local.postman_environment.json`: legacy direct-service environment

## Maintained collection behavior

The gateway collection is aligned with the current codebase:

- auth registration plus login flow through Kong
- purchase paths use `/purchase/hold/{inventoryId}` and `/purchase/confirm/{inventoryId}`
- transfer initiation uses `listingId`
- staff verification uses `POST /verify/scan`
- a fresh `test_email` is generated for each run so smoke tests do not depend on a reused shared account

## How to run

### Localhost through Kong

```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli
```

### Shared public URL

```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli
```

### Via the maintained startup script

```powershell
.\start-backend.bat
```

or:

```powershell
.\scripts\start_k8s.ps1 -RunPublicTests
```

## When to use the legacy collection

Use `TicketRemaster.postman_collection.json` only when you are debugging an individual service directly rather than validating the full gateway contract.

## Related docs

- [../README.md](../README.md)
- [../LOCAL_DEV_SETUP.md](../LOCAL_DEV_SETUP.md)
- [../TESTING.md](../TESTING.md)
