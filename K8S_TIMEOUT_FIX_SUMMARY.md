# 408 Timeout Issue - Kubernetes Fix Summary

## Problem
The frontend was receiving 408 Request Timeout errors when calling `/api/events`, causing the UI to fail after 3 retry attempts.

## Root Cause
1. **Service timeout too low**: The orchestrator service clients had a 5-second timeout, insufficient for the `/events` endpoint that makes multiple downstream calls (event service → venue service → seat inventory service).
2. **Kong proxy timeout**: Kong gateway had default timeouts that were too aggressive for complex aggregations.
3. **Missing error handling**: The frontend didn't have specific handling for 408 errors.

## Changes Made

### Backend Code (ticketremaster-b)

#### 1. Updated Service Client Timeouts
Modified `call_service()` in 4 orchestrators to use configurable timeout:
- `orchestrators/event-orchestrator/service_client.py`
- `orchestrators/qr-orchestrator/service_client.py`
- `orchestrators/marketplace-orchestrator/service_client.py`
- `orchestrators/ticket-verification-orchestrator/service_client.py`

**Changes:**
- Added `SERVICE_TIMEOUT` environment variable (default 15 seconds)
- Timeout error code: `SERVICE_UNAVAILABLE` → `SERVICE_TIMEOUT` (more specific)
- Timeout now configurable via ConfigMap instead of hardcoded

### Kubernetes Configuration (ticketremaster-b/k8s/base)

#### 1. Updated ConfigMap (`configuration.yaml`)
Added timeout configuration:
```yaml
data:
  SERVICE_TIMEOUT_SECONDS: "15"  # Increased from 5s to 15s
```

#### 2. Updated Kong Deployment (`edge-workloads.yaml`)
Added proxy timeout environment variables:
```yaml
env:
  - name: KONG_PROXY_READ_TIMEOUT
    value: "30s"
  - name: KONG_PROXY_SEND_TIMEOUT
    value: "30s"
  - name: KONG_PROXY_CONNECT_TIMEOUT
    value: "10s"
```

### Frontend (ticketremaster-f)

#### 1. Better Retry Configuration (`src/api/client.ts`)
- Initial backoff: 1s → 2s
- Max backoff: 10s → 15s
- Gives backend more time to recover between retries

#### 2. Improved Error Messages
Added specific handling for:
- `SERVICE_TIMEOUT`: "The request took too long. Please try again."
- HTTP 408: "The request timed out. Please try again."

## Deployment Steps (Kubernetes)

### 1. Rebuild and Push Container Images
The service_client.py changes are baked into the container images. You need to rebuild:

```bash
# Build all orchestrator images
docker build -t ticketremaster/event-orchestrator:latest ./orchestrators/event-orchestrator
docker build -t ticketremaster/qr-orchestrator:latest ./orchestrators/qr-orchestrator
docker build -t ticketremaster/marketplace-orchestrator:latest ./orchestrators/marketplace-orchestrator
docker build -t ticketremaster/ticket-verification-orchestrator:latest ./orchestrators/ticket-verification-orchestrator

# Push to your registry
docker push ticketremaster/event-orchestrator:latest
docker push ticketremaster/qr-orchestrator:latest
docker push ticketremaster/marketplace-orchestrator:latest
docker push ticketremaster/ticket-verification-orchestrator:latest
```

### 2. Apply Updated Kubernetes Manifests
```bash
# Navigate to k8s base directory
cd ticketremaster-b/k8s/base

# Apply updated configurations
kubectl apply -f configuration.yaml
kubectl apply -f edge-workloads.yaml

# Or use kustomize if you have a kustomization setup
kubectl apply -k .
```

### 3. Restart Pods (if not using rolling update)
```bash
# Restart orchestrator pods to pick up new ConfigMap
kubectl rollout restart deployment event-orchestrator -n ticketremaster-core
kubectl rollout restart deployment qr-orchestrator -n ticketremaster-core
kubectl rollout restart deployment marketplace-orchestrator -n ticketremaster-core
kubectl rollout restart deployment ticket-verification-orchestrator -n ticketremaster-core

# Restart Kong pods to pick up new timeout settings
kubectl rollout restart deployment kong -n ticketremaster-edge
```

### 4. Deploy Frontend Changes
```bash
cd ticketremaster-f
npm run build
# Deploy to your hosting (Vercel, etc.)
```

## Verification

### Check ConfigMap
```bash
kubectl get configmap core-runtime -n ticketremaster-core -o yaml | grep SERVICE_TIMEOUT
# Should show: SERVICE_TIMEOUT_SECONDS: "15"
```

### Check Kong Environment
```bash
kubectl get deployment kong -n ticketremaster-edge -o yaml | grep KONG_PROXY
# Should show the new timeout settings
```

### Monitor Logs
```bash
# Watch for SERVICE_TIMEOUT errors
kubectl logs -f deployment/event-orchestrator -n ticketremaster-core | grep SERVICE_TIMEOUT

# Check Kong proxy timeouts
kubectl logs -f deployment/kong -n ticketremaster-edge --container kong | grep timeout
```

### Test the Endpoint
```bash
# From frontend pod or locally
curl -H "apikey: tk_front_123456789" https://ticketremasterapi.hong-yi.me/api/events
```

## Expected Outcome
- `/events` endpoint now has up to 15 seconds to process (configurable via ConfigMap)
- Kong gateway will wait up to 30 seconds before timing out
- Frontend shows clearer error messages if timeouts occur
- Retry logic gives more time between attempts (2s, 4s, 8s with jitter)

## Configuration Tuning
If you still experience timeouts, you can increase the values in the ConfigMap:

```yaml
# In configuration.yaml
data:
  SERVICE_TIMEOUT_SECONDS: "20"  # Increase if needed
```

Then restart the orchestrator pods.

## Monitoring
Watch for these log messages:
- Backend: "SERVICE_TIMEOUT" errors in orchestrator logs
- Frontend: "The request timed out" toast messages
- Kong: Proxy timeout errors in Kong logs

## Rollback Plan
If issues persist, you can quickly revert:
```bash
# Revert ConfigMap
kubectl edit configmap core-runtime -n ticketremaster-core
# Change SERVICE_TIMEOUT_SECONDS back to "5"

# Restart pods
kubectl rollout restart deployment event-orchestrator -n ticketremaster-core
```
