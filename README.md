# TicketRemaster Backend

TicketRemaster is a Kubernetes-first backend for event discovery, seat inventory, credit top-ups, ticket purchase, QR retrieval, staff verification, resale marketplace, and peer-to-peer ticket transfer.

The repository currently contains:

- 8 Flask orchestrators for browser-facing workflows
- 13 internal services and wrappers
- 1 Socket.IO notification service
- 10 PostgreSQL databases, each owned by a single service
- Redis for short-lived workflow state and locking support
- RabbitMQ for delayed and asynchronous workflow processing
- Kong 3.9 as the only browser-facing gateway
- Cloudflare Tunnel for optional public exposure of the local cluster
- committed Kubernetes manifests under `k8s/base`

## Current Stack

- Runtime: Python 3.12 on `python:3.12-slim`
- Web framework: Flask + Flasgger
- Persistence: PostgreSQL + Flask-SQLAlchemy + Flask-Migrate
- Gateway: Kong 3.9 in DB-less declarative mode
- Messaging: RabbitMQ 3 management image
- Cache and locks: Redis 7
- Internal RPC: gRPC for seat hold and sale operations
- Payments: Stripe wrapper service
- External system of record: OutSystems credit API
- OTP integration: OutSystems notification API wrapper
- Realtime: Flask-SocketIO + Redis Pub/Sub

## Architecture

TicketRemaster is deliberately split into layers that match the committed Kubernetes namespaces.

| Layer | Namespace | Owns |
| --- | --- | --- |
| Edge | `ticketremaster-edge` | Kong, cloudflared, gateway policy |
| Core | `ticketremaster-core` | Orchestrators, services, wrappers, seed jobs |
| Data | `ticketremaster-data` | PostgreSQL StatefulSets, Redis, RabbitMQ |

### Design Logic

- Orchestrators own browser-facing workflow composition and access control.
- Atomic services own a single bounded context and, where applicable, a dedicated database.
- Kong is the only supported browser ingress. Frontends should not call internal service DNS names or direct pod ports.
- OutSystems remains the source of truth for credit balance. `credit-transaction-service` is the internal ledger, not the balance authority.
- `seat-inventory-service` owns seat-state transitions and exposes gRPC for latency-sensitive hold, release, sell, and status checks.
- Redis is used for ephemeral state such as purchase hold cache and verification locks, not as the primary record of business data.
- RabbitMQ carries delayed hold expiry and transfer notification work so those flows are not tied to synchronous request latency.

## How to Start Backend: Complete Guide

This guide walks you through setting up the TicketRemaster backend from scratch. Choose your setup path:

- **Option 1: Local Development Only** - Run backend on your laptop with local port-forwarding (no internet exposure)
- **Option 2: Public Access via Cloudflare** - Expose your local backend to the internet for remote testing or frontend collaboration

### Prerequisites

Before starting, ensure you have these tools installed and Docker Desktop is running:

| Tool | Purpose | Verify Installation |
| --- | --- | --- |
| Docker Desktop | Container runtime (must be running) | `docker --version` |
| Minikube | Local Kubernetes cluster | `minikube version` |
| kubectl | Kubernetes CLI | `kubectl version --client` |
| Node.js | Required for Newman | `node --version` |
| Newman | API testing | `newman --version` |

**If Docker Desktop is not running:**

Start it from the Start menu and wait for the whale icon to stop animating, then verify:

```powershell
docker info
```

**If any other tools are missing, install them:**

Minikube: Download from <https://minikube.sigs.k8s.io/docs/start/> and run the installer

kubectl: Download from <https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/> and place in your PATH

Newman:

```powershell
npm install -g newman
```

### First-Time Setup

#### 1. Configure Minikube Resources

Allocate enough memory and CPU for the backend stack:

```powershell
minikube config set memory 12288
minikube config set cpus 4
```

**If you're on Windows with WSL 2:**

Edit or create `C:\Users\<YourUsername>\.wslconfig`:

```ini
[wsl2]
memory=12GB
processors=4
```

Then restart WSL:

```powershell
wsl --shutdown
```

**Note:** If your machine has less than 16GB RAM, reduce memory to 8192 (8GB) but expect slower performance.

#### 2. Obtain the Secrets File

The backend requires a secrets file that contains API keys, database passwords, and other sensitive configuration.

Ask your backend maintainer for `k8s/base/secrets.local.yaml` and place it at:

```text
ticketremaster-b/k8s/base/secrets.local.yaml
```

This file is gitignored and must be obtained from the team. It typically contains:

- Cloudflare tunnel token (required for Option 2 only)
- OutSystems API keys for credit operations
- Database passwords
- Stripe and OTP wrapper secrets

**Troubleshooting:** If you have an outdated version, you may see `400` errors during registration or `401` errors during login.

#### 3. Start Minikube

Start your local Kubernetes cluster:

```powershell
minikube start
```

This will take 2-5 minutes on first run. Minikube will download the Kubernetes ISO, create a virtual machine, and configure kubectl.

Verify Minikube is running:

```powershell
minikube status
kubectl get nodes
```

You should see one node in "Ready" state.

**Troubleshooting:**

- If `minikube start` fails with "Exiting due to HOST_VIRT_UNAVAILABLE", enable virtualization in your BIOS
- If it fails with memory errors, reduce the memory allocation in step 1
- If it hangs, try `minikube delete` and then `minikube start` again

### Option 1: Local Development Setup (Localhost Only)

This setup runs the backend on your machine and exposes it only on `http://localhost:8000`. No internet exposure.

#### Start the Backend

Navigate to the `ticketremaster-b` directory and run:

```powershell
.\scripts\start_k8s.ps1
```

The script will:

1. Check prerequisites (docker, kubectl, minikube, newman)
2. Verify Minikube is running
3. Build Docker images for all services (first run takes 10-15 minutes)
4. Load images into Minikube
5. Apply Kubernetes manifests
6. Wait for all pods to be ready (data plane → core services → edge gateway)
7. Run database seed jobs
8. Open a port-forward to Kong on `http://localhost:8000`
9. Run Newman smoke tests to verify everything works

**What to Expect:**

First run (with no images built):

- Total time: 15-20 minutes
- Most time is spent building Docker images

Subsequent runs (images already built):

- Total time: 3-5 minutes
- The script detects source changes and only rebuilds when needed

**Success indicators:**

- You'll see "Done" with the local gateway URL
- A minimized PowerShell window will stay open (this is the port-forward, don't close it)
- Newman tests will show green checkmarks
- Kong is available at `http://localhost:8000`

#### Verify It's Working

Test the gateway:

```powershell
Invoke-WebRequest http://localhost:8000/events
```

You should see JSON with event data.

Configure your frontend:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_KONG_API_KEY=tk_front_123456789
```

#### Troubleshooting

**Problem: Docker Desktop is not running**

Solution: Start Docker Desktop manually from the Start menu, wait for it to fully start, then run the script again.

**Problem: Minikube is not running**

Solution: Run `minikube start` and then retry the script.

**Problem: Build fails with "no space left on device"**

Solution: Clean up Docker and retry:

```powershell
docker system prune -a --volumes
```

**Problem: Pods stuck in "ImagePullBackOff"**

Solution: Rebuild and reload images:

```powershell
.\scripts\build_k8s_images.ps1
```

**Problem: Register returns 400, then login returns 401**

This means services weren't ready when seed jobs ran.

Solution: Re-run seed jobs:

```powershell
.\scripts\rerun_k8s_seeds.ps1
```

**Problem: Port 8000 is already in use**

The startup script will automatically find an available port and tell you which one it's using. Update your frontend config to use the new port.

**Problem: Port-forward window closes unexpectedly**

Solution: Restart it manually:

```powershell
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
```

### Option 2: Public Access Setup (Cloudflare Tunnel)

This setup exposes your local backend to the internet via Cloudflare Tunnel, allowing you to access it from anywhere.

Useful for:

- Remote testing
- Sharing with frontend developers who don't want to run the backend
- Mobile device testing
- Accessing your backend from mobile devices

#### Additional Prerequisites

You need to set up your own Cloudflare Tunnel:

1. **Create a Cloudflare account** at <https://dash.cloudflare.com/sign-up> (free tier is sufficient)

2. **Add a domain to Cloudflare** (you can use a free domain from services like Freenom, or use your own domain)

3. **Create a Cloudflare Tunnel:**
   - Go to Zero Trust dashboard: <https://one.dash.cloudflare.com/>
   - Navigate to Networks → Tunnels
   - Click "Create a tunnel"
   - Choose "Cloudflared" as the connector type
   - Name your tunnel (e.g., "ticketremaster-backend")
   - Copy the tunnel token (starts with `eyJ...`)

4. **Configure the tunnel route:**
   - In the tunnel configuration, add a Public Hostname
   - Subdomain: Choose a subdomain (e.g., `api` or `ticketremaster-api`)
   - Domain: Select your domain
   - Service Type: `HTTP`
   - URL: `kong-proxy.ticketremaster-edge.svc.cluster.local:80`

5. **Add the tunnel token to your secrets file:**

   Edit `k8s/base/secrets.local.yaml` and add:

   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: cloudflare-tunnel
     namespace: ticketremaster-edge
   type: Opaque
   stringData:
     CLOUDFLARE_TUNNEL_TOKEN: "your-tunnel-token-here"
   ```

6. **Update the Newman public environment file:**

   Edit `postman/TicketRemaster.gateway-public.postman_environment.json` and change the `gateway_url` value to your Cloudflare tunnel URL:

   ```json
   { "key": "gateway_url", "value": "https://your-subdomain.your-domain.com", "type": "default", "enabled": true }
   ```

#### Start the Backend with Public Access

Navigate to the `ticketremaster-b` directory and run:

```powershell
.\scripts\start_k8s.ps1 -RunPublicTests
```

This will do everything from Option 1, plus deploy the Cloudflare tunnel connector, wait for the tunnel to establish, and run Newman smoke tests against both localhost and the public URL.

**If you only want the public URL (no local port-forward):**

```powershell
.\scripts\start_k8s.ps1 -RunPublicTests -SkipPortForward
```

**What to Expect:**

First run: 15-25 minutes (includes image building + tunnel connection time)

Subsequent runs: 4-6 minutes

**Success indicators:**

- Newman tests pass for both localhost and public URL
- Public gateway is accessible at your configured Cloudflare tunnel URL

#### Verify It's Working

Test the public gateway (replace with your actual tunnel URL):

```powershell
Invoke-WebRequest https://your-subdomain.your-domain.com/events
```

You should see JSON with event data.

Configure your frontend for public access (replace with your actual tunnel URL):

```env
VITE_API_BASE_URL=https://your-subdomain.your-domain.com
VITE_KONG_API_KEY=tk_front_123456789
```

#### Troubleshooting

**Problem: Cloudflare tunnel fails to connect**

Check the tunnel token in `secrets.local.yaml` is valid and not expired.

Check cloudflared logs:

```powershell
kubectl logs deployment/cloudflared -n ticketremaster-edge --tail=100
```

Solution: Restart the cloudflared deployment:

```powershell
kubectl rollout restart deployment/cloudflared -n ticketremaster-edge
```

**Problem: Public URL returns 502 Bad Gateway**

This means the tunnel is up but Kong is not ready yet.

Solution: Wait 1-2 minutes and try again. Check Kong logs:

```powershell
kubectl logs deployment/kong -n ticketremaster-edge --tail=100
```

**Problem: Public URL works intermittently**

The tunnel connector may be restarting.

Check cloudflared pod status:

```powershell
kubectl get pods -n ticketremaster-edge
```

If cloudflared pod is restarting, check its logs for errors.

**Problem: Public tests fail but localhost tests pass**

The tunnel may not be fully established yet.

Solution: Wait 2-3 minutes for the tunnel to stabilize, then run tests again:

```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli
```

### Manual Control (Advanced)

If you prefer full control over the startup process instead of using the automated script, follow these steps:

#### Step 1: Start the Cluster

```powershell
minikube start
```

This starts your local Kubernetes cluster. Verify it's running:

```powershell
kubectl get nodes
```

#### Step 2: Build Docker Images

Build all service and orchestrator images (first time or after code changes):

```powershell
.\scripts\build_k8s_images.ps1
```

This builds images with the tag `local-k8s-20260329` for all 20 services and orchestrators. The build process takes 10-15 minutes on first run.

Load the images into Minikube:

```powershell
minikube image load ticketremaster/user-service:local-k8s-20260329
minikube image load ticketremaster/venue-service:local-k8s-20260329
minikube image load ticketremaster/seat-service:local-k8s-20260329
minikube image load ticketremaster/event-service:local-k8s-20260329
minikube image load ticketremaster/seat-inventory-service:local-k8s-20260329
minikube image load ticketremaster/ticket-service:local-k8s-20260329
minikube image load ticketremaster/ticket-log-service:local-k8s-20260329
minikube image load ticketremaster/marketplace-service:local-k8s-20260329
minikube image load ticketremaster/transfer-service:local-k8s-20260329
minikube image load ticketremaster/credit-transaction-service:local-k8s-20260329
minikube image load ticketremaster/stripe-wrapper:local-k8s-20260329
minikube image load ticketremaster/otp-wrapper:local-k8s-20260329
minikube image load ticketremaster/auth-orchestrator:local-k8s-20260329
minikube image load ticketremaster/event-orchestrator:local-k8s-20260329
minikube image load ticketremaster/credit-orchestrator:local-k8s-20260329
minikube image load ticketremaster/ticket-purchase-orchestrator:local-k8s-20260329
minikube image load ticketremaster/qr-orchestrator:local-k8s-20260329
minikube image load ticketremaster/marketplace-orchestrator:local-k8s-20260329
minikube image load ticketremaster/transfer-orchestrator:local-k8s-20260329
minikube image load ticketremaster/ticket-verification-orchestrator:local-k8s-20260329
```

**Note:** The automated script handles this automatically and only loads missing images.

#### Step 3: Apply Kubernetes Manifests

Apply all manifests from the `k8s/base` directory:

```powershell
kubectl apply -k k8s/base
```

This creates:

- 3 namespaces: `ticketremaster-data`, `ticketremaster-core`, `ticketremaster-edge`
- 10 PostgreSQL StatefulSets (one per service database)
- Redis and RabbitMQ StatefulSets
- 20 service and orchestrator Deployments
- Kong gateway Deployment
- Cloudflared Deployment (if tunnel token is configured)
- 5 seed Jobs for initial data population
- ConfigMaps and Secrets
- Services and NetworkPolicies

#### Step 4: Wait for Data Plane

Wait for Redis and RabbitMQ to be ready before core services start:

```powershell
kubectl rollout status statefulset/redis -n ticketremaster-data --timeout=300s
kubectl rollout status statefulset/rabbitmq -n ticketremaster-data --timeout=300s
```

Wait for all database StatefulSets:

```powershell
kubectl rollout status statefulset/user-service-db -n ticketremaster-data --timeout=300s
kubectl rollout status statefulset/venue-service-db -n ticketremaster-data --timeout=300s
kubectl rollout status statefulset/seat-service-db -n ticketremaster-data --timeout=300s
kubectl rollout status statefulset/event-service-db -n ticketremaster-data --timeout=300s
kubectl rollout status statefulset/seat-inventory-service-db -n ticketremaster-data --timeout=300s
kubectl rollout status statefulset/ticket-service-db -n ticketremaster-data --timeout=300s
kubectl rollout status statefulset/ticket-log-service-db -n ticketremaster-data --timeout=300s
kubectl rollout status statefulset/marketplace-service-db -n ticketremaster-data --timeout=300s
kubectl rollout status statefulset/transfer-service-db -n ticketremaster-data --timeout=300s
kubectl rollout status statefulset/credit-transaction-service-db -n ticketremaster-data --timeout=300s
```

#### Step 5: Wait for Core Services

Wait for all core services and orchestrators to be ready:

```powershell
kubectl rollout status deployment/user-service -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/venue-service -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/seat-service -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/event-service -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/seat-inventory-service -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/ticket-service -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/ticket-log-service -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/marketplace-service -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/transfer-service -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/credit-transaction-service -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/stripe-wrapper -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/otp-wrapper -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/auth-orchestrator -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/event-orchestrator -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/credit-orchestrator -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/ticket-purchase-orchestrator -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/qr-orchestrator -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/marketplace-orchestrator -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/transfer-orchestrator -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/ticket-verification-orchestrator -n ticketremaster-core --timeout=300s
```

#### Step 6: Wait for Edge Gateway

Wait for Kong to be ready:

```powershell
kubectl rollout status deployment/kong -n ticketremaster-edge --timeout=300s
```

If using Cloudflare tunnel:

```powershell
kubectl rollout status deployment/cloudflared -n ticketremaster-edge --timeout=300s
```

#### Step 7: Wait for Seed Jobs to Complete

The seed jobs populate initial data into the databases. Wait for all jobs to complete:

```powershell
kubectl wait --for=condition=complete job --all -n ticketremaster-core --timeout=600s
```

**What the seed jobs do:**

- `seed-venues`: Creates 3 sample venues (Singapore Indoor Stadium, Esplanade Concert Hall, Marina Bay Sands)
- `seed-events`: Creates 10 sample events across different venues with various dates and pricing
- `seed-seats`: Creates seat layouts for each venue (sections, rows, seat numbers)
- `seed-seat-inventory`: Links seats to events and sets initial availability
- `seed-users`: Creates test user accounts for development

Check seed job status:

```powershell
kubectl get jobs -n ticketremaster-core
```

All jobs should show "1/1" completions. If any job failed, check its logs:

```powershell
kubectl logs job/seed-venues -n ticketremaster-core
kubectl logs job/seed-events -n ticketremaster-core
kubectl logs job/seed-seats -n ticketremaster-core
kubectl logs job/seed-seat-inventory -n ticketremaster-core
kubectl logs job/seed-users -n ticketremaster-core
```

**Verify seed data was created:**

Check that events were seeded:

```powershell
kubectl exec -n ticketremaster-core deployment/event-service -- curl -s http://localhost:5000/events
```

You should see JSON with multiple events.

**Re-running seed jobs:**

If you need to re-populate data (e.g., after database reset):

```powershell
.\scripts\rerun_k8s_seeds.ps1
```

Or manually:

```powershell
kubectl delete job seed-venues seed-events seed-seats seed-seat-inventory seed-users -n ticketremaster-core
kubectl apply -k k8s/base
kubectl wait --for=condition=complete job --all -n ticketremaster-core --timeout=600s
```

#### Step 8: Open Port-Forward

Open a port-forward to Kong (keep this terminal open while using the backend):

```powershell
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
```

Kong is now accessible at `http://localhost:8000`.

#### Step 9: Run Smoke Tests

Verify everything works with Newman:

```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli
```

The smoke tests verify:

- User registration and login
- Event listing and details
- Seat availability queries
- Credit balance checks
- Ticket purchase flow
- QR code generation
- Marketplace listing
- Transfer initiation

All tests should pass with green checkmarks.

### Checking Cluster Status

View all pods:

```powershell
kubectl get pods -n ticketremaster-edge
kubectl get pods -n ticketremaster-core
kubectl get pods -n ticketremaster-data
```

All pods should show "Running" status.

View seed jobs:

```powershell
kubectl get jobs -n ticketremaster-core
```

All jobs should show "1/1" completions.

View logs for a specific service:

```powershell
kubectl logs deployment/auth-orchestrator -n ticketremaster-core --tail=100
kubectl logs deployment/user-service -n ticketremaster-core --tail=100
```

Access RabbitMQ management UI:

```powershell
kubectl port-forward -n ticketremaster-data service/rabbitmq 15672:15672
```

Then open `http://localhost:15672` in your browser (username: `guest`, password: `guest`).

### Stopping the Backend

Stop port-forward: Close the PowerShell window running the port-forward, or press `Ctrl+C`.

Stop Minikube (preserves data):

```powershell
minikube stop
```

Delete Minikube (removes all data):

```powershell
minikube delete
```

Use `minikube delete` if you want a completely fresh start or if you're having persistent issues.

### Common Issues and Solutions

**Issue: Everything was working, now nothing works after restart**

Cause: Minikube's persistent volumes were wiped but seed jobs don't re-run automatically.

Solution: Re-run seed jobs:

```powershell
.\scripts\rerun_k8s_seeds.ps1
```

Or delete and reapply the jobs:

```powershell
kubectl delete job seed-venues seed-events seed-seats seed-seat-inventory seed-users -n ticketremaster-core
kubectl apply -k k8s/base
kubectl wait --for=condition=complete job --all -n ticketremaster-core --timeout=600s
```

**Issue: Services are crashing with database connection errors**

Cause: Database passwords in `secrets.local.yaml` don't match what the databases expect.

Solution: Get the latest `secrets.local.yaml` from your backend maintainer and reapply:

```powershell
kubectl delete -k k8s/base
kubectl apply -k k8s/base
```

**Issue: Out of disk space**

Cause: Docker images and Minikube volumes accumulate over time.

Solution: Clean up Docker:

```powershell
docker system prune -a --volumes
minikube delete
minikube start
```

Then rebuild:

```powershell
.\scripts\build_k8s_images.ps1
```

**Issue: Minikube won't start after Windows update**

Cause: Windows updates sometimes break virtualization or Docker.

Solution:

1. Restart Docker Desktop
2. Try `minikube delete` then `minikube start`
3. If still failing, reinstall Minikube

**Issue: Newman tests fail with timeout errors**

Cause: Services are still starting up or are overloaded.

Solution: Wait 1-2 minutes and run tests again:

```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli
```

## Public and Local Surfaces

- **Local gateway:** `http://localhost:8000` (when port-forward is active)
- **Public gateway:** Your configured Cloudflare tunnel URL (e.g., `https://api.yourdomain.com`)
- **RabbitMQ management:** `http://localhost:15672` (after port-forwarding `svc/rabbitmq`)

Frontends should use the no-prefix routes such as `/auth/login` and `/events`. Kong also supports `/api/...` compatibility aliases, but new frontend code should use the no-prefix form.

## Browser-Facing Routes

| Route group | Current paths |
| --- | --- |
| Auth | `/auth/register`, `/auth/verify-registration`, `/auth/login`, `/auth/me`, `/auth/logout`, `/auth/logout-all` |
| Events and venues | `/venues`, `/events`, `/events/{eventId}`, `/events/{eventId}/seats`, `/events/{eventId}/seats/{inventoryId}`, `/admin/events`, `/admin/events/{eventId}/dashboard` |
| Credits | `/credits/balance`, `/credits/topup/initiate`, `/credits/topup/confirm`, `/credits/topup/webhook`, `/credits/transactions` |
| Purchase | `/purchase/hold/{inventoryId}`, `DELETE /purchase/hold/{inventoryId}`, `/purchase/confirm/{inventoryId}` |
| Tickets and QR | `/tickets`, `/tickets/{ticketId}/qr` |
| Marketplace | `/marketplace`, `/marketplace/list`, `DELETE /marketplace/{listingId}` |
| Transfer | `/transfer/initiate`, `/transfer/pending`, `/transfer/{transferId}`, `/transfer/{transferId}/seller-accept`, `/transfer/{transferId}/seller-reject`, `/transfer/{transferId}/buyer-verify`, `/transfer/{transferId}/seller-verify`, `/transfer/{transferId}/resend-otp`, `/transfer/{transferId}/cancel` |
| Staff verification | `/verify/scan`, `/verify/manual` |
| Stripe ingress | `/webhooks/stripe` |

## Development Workflow

### Making Code Changes

After modifying service or orchestrator code:

Rebuild images:

```powershell
.\scripts\build_k8s_images.ps1
```

Restart affected deployments:

```powershell
# Restart specific service
kubectl rollout restart deployment/user-service -n ticketremaster-core

# Or restart all core services
kubectl rollout restart deployment -n ticketremaster-core
```

Wait for rollout to complete:

```powershell
kubectl rollout status deployment/user-service -n ticketremaster-core
```

The startup script automatically detects code changes and rebuilds images when needed.

### Running Tests

The repository includes Newman smoke tests that verify the gateway and all major workflows.

Run localhost tests:

```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli
```

Run public tests:

```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli
```

### Viewing Service Documentation

Each service exposes Swagger/Flasgger documentation at its `/apidocs` endpoint.

To access it:

Port-forward to the service:

```powershell
kubectl port-forward -n ticketremaster-core deployment/user-service 5000:5000
```

Open `http://localhost:5000/apidocs` in your browser.

## For Frontend Developers

If you only need to consume the backend and don't want to run it locally, you have two options:

**Option A: Use a shared backend instance**

If your team has a shared backend instance running with a Cloudflare tunnel, use that URL:

```env
VITE_API_BASE_URL=https://your-team-backend-url.com
VITE_KONG_API_KEY=tk_front_123456789
```

**Option B: Set up your own Cloudflare tunnel**

Follow the instructions in "Option 2: Public Access Setup" above to expose your local backend to the internet.

**Note:** Shared backend instances should not be used for destructive testing or load testing.
