# Local Development Setup

---

## Already set up? Just starting Minikube again?

If you've done the first-time setup before, this is all you need:

```powershell
minikube start
kubectl apply -k k8s/base
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
```

Wait ~2 minutes for pods to be ready, then your frontend works at `http://localhost:8000`.

To verify everything is healthy:

```powershell
kubectl get pods --all-namespaces
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli
```

> The public URL (`https://ticketremasterapi.hong-yi.me`) works automatically once cloudflared reconnects — no port-forward needed for that.

---

## Prerequisites

| Tool | Version | Install |
| --- | --- | --- |
| Node.js | `^20.19.0` or `>=22.12.0` | [nodejs.org](https://nodejs.org) |
| kubectl | any recent | [Install guide](https://kubernetes.io/docs/tasks/tools/) |
| Minikube | any recent | [Install guide](https://minikube.sigs.k8s.io/docs/start/) |
| newman | any recent | `npm install -g newman` |
| Docker Desktop | any recent | [docker.com](https://www.docker.com/products/docker-desktop/) |

---

## Two ways to connect

### Option A — Public Cloudflare URL (easiest, no Minikube needed)

The backend is live at `https://ticketremasterapi.hong-yi.me`. No port-forwarding or Minikube required.

Set in your frontend `.env.local`:

```env
VITE_API_BASE_URL=https://ticketremasterapi.hong-yi.me
```

Skip to [Frontend Setup](#frontend-setup).

---

### Option B — Run Minikube yourself

#### First-time setup

**Step 1 — Configure Minikube memory (once per machine)**

```bash
minikube config set memory 12288
minikube config set cpus 4
```

Also set in `C:\Users\<you>\.wslconfig` (Windows):

```ini
[wsl2]
memory=12GB
```

Then run `wsl --shutdown` and restart Docker Desktop.

**Step 2 — Get secrets file**

`k8s/base/secrets.local.yaml` is gitignored. Ask the backend maintainer for this file and place it at `k8s/base/secrets.local.yaml` before continuing.

**Step 3 — Start Minikube**

```bash
minikube start
```

> If you previously ran Minikube with less memory, delete and recreate: `minikube delete && minikube start`

**Step 4 — Build and load images (first time or after `minikube delete`)**

```powershell
# Build all images (~5 mins)
.\scripts\build_k8s_images.ps1

# Load into Minikube (~10 mins)
$tag = "local-k8s-20260329"
$images = @(
  "user-service","venue-service","seat-service","event-service",
  "seat-inventory-service","ticket-service","ticket-log-service",
  "marketplace-service","transfer-service","credit-transaction-service",
  "stripe-wrapper","otp-wrapper","auth-orchestrator","event-orchestrator",
  "credit-orchestrator","ticket-purchase-orchestrator","qr-orchestrator",
  "marketplace-orchestrator","transfer-orchestrator","ticket-verification-orchestrator"
)
foreach ($img in $images) { minikube image load "ticketremaster/${img}:${tag}" }
```

> After `minikube stop` / `minikube start`, images persist — no reload needed. Only reload after `minikube delete`.

**Step 5 — Apply manifests**

```bash
kubectl apply -k k8s/base
```

**Step 6 — Wait for pods**

```bash
kubectl get pods --all-namespaces --watch
```

All pods should show `1/1 Running`. Takes 2–5 minutes on first run.

**Step 7 — Run migrations (first time only)**

```bash
kubectl exec -n ticketremaster-core deployment/user-service -- flask db upgrade
```

**Step 8 — Port-forward Kong**

```bash
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
```

Keep this terminal open. Kong is now at `http://localhost:8000`.

---

#### Every subsequent start (already set up)

```bash
minikube start
kubectl apply -k k8s/base
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
```

That's it. No image loading, no migrations, no rebuilding.

---

## Frontend Setup

**1. Install dependencies**

```bash
cd ticketremaster-f
npm install
```

**2. Create env file**

```bash
cp .env.example .env.local
```

Edit `.env.local`:

```env
# Option A — public URL (no Minikube needed):
VITE_API_BASE_URL=https://ticketremasterapi.hong-yi.me

# Option B — local Minikube (requires port-forward running):
# VITE_API_BASE_URL=http://localhost:8000

# Kong API key
VITE_KONG_API_KEY=tk_front_123456789

# Stripe public key (test mode)
VITE_STRIPE_PUBLIC_KEY=pk_test_51T2WUnLMrVGaDjow...

# Leave blank for local dev
VITE_SENTRY_DSN=
VITE_POSTHOG_API_KEY=
```

**3. Start dev server**

```bash
npm run dev
```

Frontend runs at `http://localhost:5173`.

---

## API Routes Reference

All requests go to `VITE_API_BASE_URL` — no `/api` prefix. Kong routes them internally.

### Auth

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| POST | `/auth/register` | none | Rate limited: 5/min |
| POST | `/auth/login` | none | Rate limited: 10/min |
| POST | `/auth/verify-registration` | none | OTP phone verification |
| GET | `/auth/me` | JWT | Current user profile |
| POST | `/auth/logout` | JWT | Revoke token |

### Events & Venues

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| GET | `/events` | none | Supports `?type=&page=&limit=` |
| GET | `/events/:id` | none | Event detail with venue |
| GET | `/events/:id/seats` | none | Seat map with availability |
| GET | `/events/:id/seats/:inventoryId` | none | Single seat detail |
| GET | `/venues` | none | All venues |
| POST | `/admin/events` | admin JWT | Create event |
| GET | `/admin/events/:id/dashboard` | admin JWT | Event analytics |

### Purchase

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| POST | `/purchase/hold/:inventoryId` | JWT + apikey | 5-min hold, distributed lock |
| DELETE | `/purchase/hold/:inventoryId` | JWT + apikey | Release hold early |
| POST | `/purchase/confirm/:inventoryId` | JWT + apikey | Use `Idempotency-Key` header |

### Tickets

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| GET | `/tickets` | JWT + apikey | My tickets |
| GET | `/tickets/:id/qr` | JWT + apikey | QR code (1-min expiry) |

### Credits

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| GET | `/credits/balance` | JWT + apikey | Current balance |
| POST | `/credits/topup/initiate` | JWT + apikey | Returns Stripe clientSecret |
| POST | `/credits/topup/confirm` | JWT + apikey | Use `Idempotency-Key` header |
| GET | `/credits/transactions` | JWT + apikey | Transaction history |

### Marketplace

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| GET | `/marketplace` | none | Supports `?eventId=&page=&limit=` |
| POST | `/marketplace/list` | JWT + apikey | List a ticket for sale |
| DELETE | `/marketplace/:listingId` | JWT + apikey | Remove listing |

### Transfer (P2P)

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| POST | `/transfer/initiate` | JWT + apikey | Start transfer from listing |
| GET | `/transfer/pending` | JWT + apikey | My pending transfers |
| GET | `/transfer/:id` | JWT + apikey | Transfer status |
| POST | `/transfer/:id/seller-accept` | JWT + apikey | Seller accepts |
| POST | `/transfer/:id/seller-reject` | JWT + apikey | Seller rejects |
| POST | `/transfer/:id/buyer-verify` | JWT + apikey | Buyer OTP — rate limited: 3/15min |
| POST | `/transfer/:id/seller-verify` | JWT + apikey | Seller OTP — rate limited: 3/15min |
| POST | `/transfer/:id/resend-otp` | JWT + apikey | Resend OTP |
| POST | `/transfer/:id/cancel` | JWT + apikey | Cancel transfer |

### Verification (Staff)

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| POST | `/verify/scan` | staff JWT + apikey | Scan QR hash |
| POST | `/verify/manual` | staff JWT + apikey | Manual ticket ID lookup |

### Webhooks

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| POST | `/webhooks/stripe` | Stripe signature | Backend-to-backend only |

---

## Test Accounts

| Role | How to get |
| --- | --- |
| Regular user | Register a new account via `/auth/register` |
| Admin | Ask the backend maintainer |
| Staff | Ask the backend maintainer |

---

## Troubleshooting

### Known Issues & Fixes

#### Stale Cloudflare connectors causing 503s on public URL

**Symptom:** `https://ticketremasterapi.hong-yi.me/events` returns 503 but `http://localhost:8000/events` works.

**Cause:** Multiple cloudflared connectors from old Minikube restarts. Cloudflare load-balances across all — stale ones point to dead backends.

**Fix (PowerShell):**

```powershell
$h = @{"X-Auth-Email"="<your-cf-email>";"X-Auth-Key"="<your-global-api-key>";"Content-Type"="application/json"}
$a = "<account-id>"; $t = "<tunnel-id>"

# List connectors
(Invoke-WebRequest "https://api.cloudflare.com/client/v4/accounts/$a/cfd_tunnel/$t/connections" -Headers $h -UseBasicParsing).Content | ConvertFrom-Json | Select -Expand result | ForEach-Object { Write-Host "$($_.id) | $($_.arch) | $(($_.conns|Select -First 1).origin_ip)" }

# Delete a stale one
Invoke-WebRequest "https://api.cloudflare.com/client/v4/accounts/$a/cfd_tunnel/$t/connections?client_id=<id>" -Method DELETE -Headers $h -UseBasicParsing
```

Keep only connectors matching your current machine's IP. Delete all others.

**Prevention:** cloudflared and Kong are set to `replicas: 1` in the manifests — never scale them up.

---

#### cloudflared Windows service keeps reconnecting

**Symptom:** A `windows_amd64` connector reappears in Cloudflare dashboard after deletion.

**Fix (admin PowerShell):**

```powershell
sc.exe stop cloudflared
sc.exe config cloudflared start= disabled
```

---

#### Minikube OOM / kubectl TLS timeout

**Symptom:** `kubectl` hangs or returns `net/http: TLS handshake timeout`.

**Fix:**

```bash
minikube delete
minikube config set memory 12288
minikube start
```

Ensure `.wslconfig` has `memory=12GB`, then `wsl --shutdown` before starting.

---

#### RabbitMQ CrashLoopBackOff

**Symptom:** `rabbitmq-0` crashes with `RABBITMQ_VM_MEMORY_HIGH_WATERMARK is set but deprecated`.

**Fix:** Already fixed in current manifests. Pull latest and `kubectl apply -k k8s/base`.

---

#### Auth orchestrator OOM / login returns 401 or 502

**Symptom:** Login intermittently fails via public URL.

**Fix:** Already fixed — auth orchestrator runs 2 gunicorn workers with 512MB limit. Pull latest manifests.

---

#### ImagePullBackOff after minikube delete

**Symptom:** Core pods stuck in `ImagePullBackOff`.

**Fix:** Reload images (Step 4 above). `minikube delete` wipes the image registry.

---

#### Port-forward drops after idle

**Fix:** Restart it:

```bash
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
```

---

#### CORS errors in browser

- `VITE_API_BASE_URL` must have no trailing slash and correct protocol.
- CORS allowlist includes `http://localhost:5173` only — other ports won't work.

---

#### 401 on protected routes

- Session expired (JWT TTL is 24h) — log in again.
- `VITE_KONG_API_KEY=tk_front_123456789` must be set in `.env.local`.

---

#### Pod stuck in Init or CrashLoopBackOff

```bash
kubectl describe pod <pod-name> -n ticketremaster-core
kubectl logs <pod-name> -n ticketremaster-core
```

---

#### Secrets missing

You are missing `k8s/base/secrets.local.yaml`. Ask the backend maintainer.

---

### Setting up your own Cloudflare Tunnel

If you want your own public URL instead of the shared one:

1. Create a Cloudflare account, add your domain
2. Zero Trust → Networks → Tunnels → Create tunnel → copy the token
3. Update `k8s/base/secrets.local.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: edge-secrets
  namespace: ticketremaster-edge
type: Opaque
stringData:
  CLOUDFLARE_TUNNEL_TOKEN: "<your-token>"
```

4. In the Cloudflare tunnel dashboard, add a public hostname route:
   - Hostname: `<your-subdomain>.<your-domain>`
   - Service: `http://kong-proxy.ticketremaster-edge.svc.cluster.local:80`
5. Update `postman/TicketRemaster.gateway-public.postman_environment.json` with your URL
6. `kubectl apply -k k8s/base`

Keep cloudflared at `replicas: 1` — multiple replicas cause stale connector accumulation.

---

## Notes for the Backend Maintainer

- `k8s/base/secrets.local.yaml` is gitignored — share out-of-band (encrypted message, password manager).
- After pulling new backend changes:

```bash
docker build -t ticketremaster/<service>:local-k8s-20260329 -f <service>/Dockerfile .
minikube image load ticketremaster/<service>:local-k8s-20260329
kubectl rollout restart deployment/<service> -n ticketremaster-core
```

- After config changes:

```bash
kubectl apply -k k8s/base
kubectl rollout restart deployment/kong -n ticketremaster-edge
```
