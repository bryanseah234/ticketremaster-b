# Services Index

This folder contains the atomic services and wrappers that sit behind the orchestrator layer.

## Service groups

### Core data services

- [user-service/README.md](user-service/README.md)
- [venue-service/README.md](venue-service/README.md)
- [seat-service/README.md](seat-service/README.md)
- [event-service/README.md](event-service/README.md)
- [seat-inventory-service/README.md](seat-inventory-service/README.md)
- [ticket-service/README.md](ticket-service/README.md)
- [ticket-log-service/README.md](ticket-log-service/README.md)
- [marketplace-service/README.md](marketplace-service/README.md)
- [transfer-service/README.md](transfer-service/README.md)
- [credit-transaction-service/README.md](credit-transaction-service/README.md)

### Wrappers and infrastructure-facing services

- [stripe-wrapper/README.md](stripe-wrapper/README.md)
- [otp-wrapper/README.md](otp-wrapper/README.md)
- [notification-service/README.md](notification-service/README.md)

## Design role

Atomic services own:

- one bounded context
- one database or one external integration surface
- narrow, internal HTTP or gRPC contracts

They do not own browser aggregation or gateway policy. That remains the orchestrator and Kong responsibility.

## Related docs

- [../README.md](../README.md)
- [../INSTRUCTION.md](../INSTRUCTION.md)
- [../TESTING.md](../TESTING.md)
