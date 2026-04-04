# Local Development Setup

This guide explains how to run the **frontend locally** against the **Minikube-hosted backend** (managed by one team member).

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Node.js | `^20.19.0` or `>=22.12.0` | [nodejs.org](https://nodejs.org) |
| kubectl | any recent | [Install guide](https://kubernetes.io/docs/tasks/tools/) |
| Minikube | any recent | [Install guide](https://minikube.sigs.k8s.io/docs/start/) |

You do **not** need Docker or Python to run the frontend against the shared backend.

---

## Two ways to connect

### Option A — Use the public Cloudflare URL (easiest, no Minikube needed)

The backend is exposed publicly via Cloudflare Tunnel. No port-forwarding or Minikube required.

Set `VITE_API_BASE_URL` to the public API URL in your `.env.local`:

```
VITE_API_BASE_URL=https://ticketremasterapi.hong-yi.me
```

Skip to [Frontend Setup](#frontend-setup).

---

### Option B — Run Minikube yourself (offline / own instance)

Use this if you want to run the full backend stack on your own machine.

#### 1. Start Minikube

```bash
minikube start --memory=6144 --cpus=4
```

#### 2. Apply the Kubernetes manifests

```bash
cd ticketremaster-b
kubectl apply -k k8s/base
```

> **Note:** `k8s/base/secrets.local.yaml` is gitignored. Get this file from the team member who manages the backend — it contains real API keys and DB passwords. Place it at `k8s/base/secrets.local.yaml` before running `kubectl apply -k`.

#### 3. Wait for all pods to be Ready

```bash
kubectl get pods -n ticketremaster-core --watch
kubectl get pods -n ticketremaster-data --watch
kubectl get pods -n ticketremaster-edge --watch
```

All pods should show `Running` and `1/1` (or `2/2` for init-container pods). This can take 2–5 minutes on first run.

#### 4. Run database migrations

On first setup only, migrations must be run for any service that uses a DB:

```bash
kubectl exec -n ticketremaster-core deployment/user-service -- flask db upgrade
```

#### 5. Port-forward Kong to localhost

```bash
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
```

Leave this terminal open. Kong is now reachable at `http://localhost:8000`.

Set `VITE_API_BASE_URL` in your `.env.local`:

```
VITE_API_BASE_URL=http://localhost:8000
```

---

## Frontend Setup

#### 1. Clone the frontend repo and install dependencies

```bash
cd ticketremaster-f
npm install
```

#### 2. Create your local env file

```bash
cp .env.example .env.local
```

Edit `.env.local` with the correct values:

```env
# Point to the backend (choose Option A or B above)
VITE_API_BASE_URL=https://ticketremasterapi.hong-yi.me

# Kong API key — matches the frontend_app consumer in Kong config
VITE_KONG_API_KEY=tk_front_123456789

# Stripe public key (test mode)
VITE_STRIPE_PUBLIC_KEY=pk_test_51T2WUnLMrVGaDjow...

# Leave these blank or as-is for local dev
VITE_SENTRY_DSN=
VITE_POSTHOG_API_KEY=
```

> `.env.local` is gitignored — never commit it.

#### 3. Start the dev server

```bash
npm run dev
```

Frontend runs at `http://localhost:5173`.

---

## Test Accounts

Use these to log in without registering:

| Role | Email | Password |
|---|---|---|
| Regular user | *(register a new account)* | — |
| Admin | *(ask the backend maintainer)* | — |
| Staff | *(ask the backend maintainer)* | — |

---

## API Routes Reference

All frontend requests go to `VITE_API_BASE_URL` directly — **no `/api` prefix**. Kong routes them internally.

| Feature | Method | Path |
|---|---|---|
| Register | POST | `/auth/register` |
| Verify phone (OTP) | POST | `/auth/verify-registration` |
| Login | POST | `/auth/login` |
| Get current user | GET | `/auth/me` |
| List events | GET | `/events` |
| Event detail | GET | `/events/:id` |
| Seat map | GET | `/events/:id/seats` |
| Hold seat | POST | `/purchase/hold/:inventoryId` |
| Release hold | DELETE | `/purchase/hold/:inventoryId` |
| Confirm purchase | POST | `/purchase/confirm/:inventoryId` |
| My tickets | GET | `/tickets` |
| Ticket QR | GET | `/tickets/:id/qr` |
| Credit balance | GET | `/credits/balance` |
| Marketplace | GET | `/marketplace` |
| List ticket | POST | `/marketplace/list` |
| Transfer | POST | `/transfer/initiate` |
| Verify ticket (staff) | POST | `/verify/scan` |
| Admin: create event | POST | `/admin/events` |
| Admin: event dashboard | GET | `/admin/events/:id/dashboard` |

---

## Troubleshooting

**CORS errors in browser console**
- Make sure `VITE_API_BASE_URL` matches exactly (no trailing slash, correct protocol).
- The backend CORS allowlist includes `http://localhost:5173`. Other ports won't work.

**401 Unauthorized on protected routes**
- Your session may have expired (JWT TTL is 24 hours). Log in again.
- Make sure `VITE_KONG_API_KEY=tk_front_123456789` is set in `.env.local`.

**404 on any `/api/...` route**
- Kong may still be starting up. Check: `kubectl get pods -n ticketremaster-edge`
- Make sure port-forward is still running (Option B only).

**502 Bad Gateway**
- An upstream service may be restarting. Check: `kubectl get pods -n ticketremaster-core`
- Wait 30 seconds and retry.

**Pod stuck in `Init:0/1` or `CrashLoopBackOff`**
```bash
# Check what's wrong
kubectl describe pod <pod-name> -n ticketremaster-core
kubectl logs <pod-name> -n ticketremaster-core
```

**Secrets missing / services logging "Missing required secret"**
- You are missing `k8s/base/secrets.local.yaml`. Ask the backend maintainer for this file.

---

## Replica Scaling (Minikube only)

The default manifests set all deployments to `replicas: 1`. On a single Minikube node, scaling everything to 2 simultaneously causes a DNS storm that crashes CoreDNS (all init containers query DNS at once, overloading it).

**Recommended approach for HA on Minikube:**

Scale only the stateless orchestrators to 2 — they have no init containers and start instantly. Keep DB-backed services at 1.

```bash
# Scale orchestrators to 2 (safe — no init containers)
kubectl scale deployment \
  auth-orchestrator credit-orchestrator event-orchestrator \
  marketplace-orchestrator qr-orchestrator \
  ticket-purchase-orchestrator ticket-verification-orchestrator \
  transfer-orchestrator \
  -n ticketremaster-core --replicas=2

# Also scale Kong and cloudflared
kubectl scale deployment kong cloudflared -n ticketremaster-edge --replicas=2
```

Wait 60 seconds between each group if you want to be safe. Do **not** scale all 20 services at once.

**If CoreDNS crashes** (symptom: all pods show `Temporary failure in name resolution`):

```bash
# Restart CoreDNS
kubectl delete pod -n kube-system -l k8s-app=kube-dns

# Scale everything back to 1 first, let it stabilize, then scale up gradually
kubectl scale deployment --all -n ticketremaster-core --replicas=1
```

---

## Notes for the Backend Maintainer

- `k8s/base/secrets.local.yaml` is gitignored. Share it with teammates out-of-band (e.g. encrypted message, shared password manager).
- After pulling new backend changes, rebuild and reload affected images:
  ```bash
  docker build -t ticketremaster/<service-name>:local-k8s-20260329 \
    -f <service-path>/Dockerfile .
  minikube image load ticketremaster/<service-name>:local-k8s-20260329
  kubectl rollout restart deployment/<service-name> -n ticketremaster-core
  ```
- Re-apply the full stack after config changes:
  ```bash
  kubectl apply -k k8s/base
  kubectl rollout restart deployment/kong -n ticketremaster-edge
  ```
