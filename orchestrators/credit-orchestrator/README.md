# credit-orchestrator

Credit Orchestrator coordinates credit balance reads, top-up initiation, Stripe webhook completion, and credit transaction logging.

## Current Status

- Folder exists as a planned orchestrator module.
- Runtime implementation files are not built yet.
- Stripe webhook handling currently lives in `services/stripe-wrapper`; this orchestrator is the target long-term webhook integration point.

## Planned Frontend-Facing Endpoints

- `GET /credits/balance`
- `POST /credits/topup/initiate`
- `POST /credits/topup/webhook`
- `GET /credits/transactions`

Source contract: [../../FRONTEND.md](../../FRONTEND.md).

## Downstream Dependencies

- `stripe-wrapper` for payment intent creation and signature-verified webhook event payload
- OutSystems credit service for actual balance mutation/read
- `credit-transaction-service` for idempotency and transaction history

## Stripe Webhook Ownership Model

- Until this orchestrator is implemented, use `stripe listen --forward-to localhost:5011/stripe/webhook`.
- After this orchestrator is implemented and exposes `POST /credits/topup/webhook`, move listener target to orchestrator path.
- Webhook route must remain unauthenticated and rely on Stripe signature validation.

## Implementation Notes

- enforce idempotency by `paymentIntentId` before applying top-up
- only update balance after verified webhook event (`payment_intent.succeeded`)
- log transaction after successful balance update
- return deterministic error codes for retry-safe handling

## Related Docs

- Orchestrator index: [../README.md](../README.md)
- Stripe wrapper current behavior: [../../services/stripe-wrapper/README.md](../../services/stripe-wrapper/README.md)
- Testing Stripe CLI flow: [../../TESTING.md](../../TESTING.md)
- Implementation guidance: [../../INSTRUCTION.md](../../INSTRUCTION.md)
- Orchestration patterns: [../../.github/skills/orchestrator-flow/SKILL.md](../../.github/skills/orchestrator-flow/SKILL.md)

