# stripe-wrapper

`stripe-wrapper` isolates Stripe-specific logic from the rest of the platform.

## Design role

- creates PaymentIntents for credit top-up
- retrieves PaymentIntent details for confirm-path checks
- verifies Stripe webhook signatures
- keeps Stripe SDK details out of orchestrator code

## Current routes

- `GET /health`
- `POST /stripe/create-payment-intent`
- `POST /stripe/retrieve-payment-intent`
- `POST /stripe/webhook`

## Runtime notes

- no service-owned database
- driven by Stripe secrets from `secrets.local.yaml`
- called by `credit-orchestrator`

## Local verification

```powershell
python -m pytest -p no:cacheprovider services/stripe-wrapper/tests
```

Related docs:

- [../README.md](../README.md)
- [../../API.md](../../API.md)
