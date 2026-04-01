# OBSERVABILITY VERIFICATION

This document provides a quick, repeatable verification flow for backend observability in TicketRemaster.

## Scope

Covers:
- Sentry error/event verification for backend services
- PostHog frontend analytics verification references
- Basic log and trace correlation checks

## Prerequisites

- Backend stack is running (`docker compose up -d`)
- Correct `.env` values are configured for Sentry DSNs and PostHog keys
- You have access to the relevant Sentry and PostHog projects

## 1) Verify Sentry from Backend

Use a running service container (or local venv) and emit a controlled message and exception:

```python
import sentry_sdk

sentry_sdk.capture_message("ticketremaster observability smoke test")
try:
    raise RuntimeError("ticketremaster sentry verification exception")
except Exception as exc:
    sentry_sdk.capture_exception(exc)
```

Expected result:
- Message appears in Sentry issue/event stream
- Exception appears with stack trace and service tags

## 2) Verify Error Path via API

Trigger a known validation failure from an orchestrator endpoint and confirm:
- client receives expected HTTP status code
- service logs include trace/correlation ID
- Sentry captures the error (if configured to capture handled errors)

## 3) Verify PostHog (Frontend)

For frontend telemetry checks, use the frontend testing guide and validate:
- page view events
- key workflow events (login, browse events, purchase intent)
- user/session properties

Reference docs:
- [FRONTEND.md](FRONTEND.md)
- [TESTING.md](TESTING.md)

## 4) Cross-check Logs

Use container logs for quick verification:

```bash
docker compose logs --tail=200 auth-orchestrator
docker compose logs --tail=200 ticket-purchase-orchestrator
docker compose logs --tail=200 notification-service
```

Confirm that timestamps and request/trace IDs align with Sentry events.

## 5) Minimum Done Criteria

- At least one backend Sentry message event confirmed
- At least one backend Sentry exception event confirmed
- API error flow validated with matching logs
- PostHog event visibility confirmed (frontend side)

## Related Documentation

- [README.md](README.md)
- [COMPLETE_SYSTEM_DOCUMENTATION.md](COMPLETE_SYSTEM_DOCUMENTATION.md)
- [TESTING.md](TESTING.md)
- [services/notification-service/NOTIFICATIONS.md](services/notification-service/NOTIFICATIONS.md)
