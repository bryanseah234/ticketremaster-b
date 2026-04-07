# TicketRemaster Backend Testing Guide

This repository is tested at three levels:

- gateway smoke tests through Kong
- service and orchestrator pytest suites
- Kubernetes readiness and runtime verification

The maintained local flow is Kubernetes-first. Docker Compose may still exist in the repo for isolated service work, but the current system-level source of truth is the Minikube stack under `k8s/base`.

## Recommended smoke flow

### One-command path

```powershell
.\start-backend.bat
```

### PowerShell path

```powershell
.\scripts\start_k8s.ps1
```

Optional public verification after Cloudflare reconnects:

```powershell
.\scripts\start_k8s.ps1 -RunPublicTests
```

## Gateway smoke suite

The maintained collection is:

```text
postman/TicketRemaster.gateway.postman_collection.json
```

Key behavior of the current collection:

- runs against Kong, not direct service ports
- generates a fresh `test_email` for each run
- uses the current purchase routes with `inventoryId` in the path
- uses the current transfer route with `listingId`
- uses the current staff verification path `POST /verify/scan`

### Localhost run

```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli
```

### Public run

```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli
```

## What the smoke suite proves

- Kong routing is alive
- auth registration and login work end-to-end
- a JWT is issued and reused for protected routes
- current public routes match the committed orchestrator code
- key-auth protected gateway routes reject missing credentials

## Common smoke failures

### Register `400`, then protected routes `401`

This usually means the first auth request failed before a JWT was created. Most often:

- downstream auth dependencies were not ready yet
- seed jobs were still running
- the cluster was tested before port-forward or Cloudflare had settled

Check:

```powershell
kubectl get pods -n ticketremaster-core
kubectl get jobs -n ticketremaster-core
kubectl logs deployment/auth-orchestrator -n ticketremaster-core --tail=100
kubectl logs deployment/user-service -n ticketremaster-core --tail=100
```

### Protected routes return `401`

Verify both headers are being sent where required:

- `Authorization: Bearer <jwt>`
- `apikey: tk_front_123456789`

### Credit routes return `503`

That normally points to the external OutSystems dependency rather than to Kong itself.

### Marketplace or transfer creation returns `400` or `404`

That is valid when the smoke run has not purchased a ticket first, or when a listing is intentionally missing.

## Kubernetes verification

### Pods and jobs

```powershell
kubectl get pods -n ticketremaster-edge
kubectl get pods -n ticketremaster-core
kubectl get pods -n ticketremaster-data
kubectl get jobs -n ticketremaster-core
```

### Logs

```powershell
kubectl logs deployment/kong -n ticketremaster-edge --tail=100
kubectl logs deployment/auth-orchestrator -n ticketremaster-core --tail=100
kubectl logs deployment/ticket-purchase-orchestrator -n ticketremaster-core --tail=100
kubectl logs deployment/transfer-orchestrator -n ticketremaster-core --tail=100
```

### Readiness

```powershell
kubectl rollout status deployment/kong -n ticketremaster-edge --timeout=300s
kubectl wait --for=condition=available deployment --all -n ticketremaster-core --timeout=300s
kubectl wait --for=condition=complete job --all -n ticketremaster-core --timeout=600s
```

## Service and orchestrator pytest suites

Run from the repo root unless a README says otherwise.

### Whole-repo checks

```powershell
python -m pytest
```

### Targeted examples

```powershell
python -m pytest -p no:cacheprovider services/user-service/tests
python -m pytest -p no:cacheprovider services/seat-inventory-service/tests
python -m pytest -p no:cacheprovider orchestrators/ticket-purchase-orchestrator/tests
python -m pytest -p no:cacheprovider orchestrators/transfer-orchestrator/tests
```

Notes:

- most service tests use isolated test databases or in-memory SQLite fixtures
- `tests/test_rabbitmq_integration.py` expects RabbitMQ reachability
- gRPC tests live in `services/seat-inventory-service/tests`

## Manual checks by subsystem

### RabbitMQ

```powershell
kubectl port-forward -n ticketremaster-data service/rabbitmq 15672:15672
```

Open `http://localhost:15672`.

### Redis

```powershell
kubectl exec -n ticketremaster-data statefulset/redis -- redis-cli ping
```

### Kong

```powershell
Invoke-WebRequest http://localhost:8000/events
```

### Public edge

```powershell
Invoke-WebRequest https://ticketremasterapi.hong-yi.me/events
```

## Related docs

- [README.md](README.md)
- [LOCAL_DEV_SETUP.md](LOCAL_DEV_SETUP.md)
- [API.md](API.md)
- [FRONTEND.md](FRONTEND.md)
- [postman/README.md](postman/README.md)
