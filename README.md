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

## Current stack

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

### Design logic

- Orchestrators own browser-facing workflow composition and access control.
- Atomic services own a single bounded context and, where applicable, a dedicated database.
- Kong is the only supported browser ingress. Frontends should not call internal service DNS names or direct pod ports.
- OutSystems remains the source of truth for credit balance. `credit-transaction-service` is the internal ledger, not the balance authority.
- `seat-inventory-service` owns seat-state transitions and exposes gRPC for latency-sensitive hold, release, sell, and status checks.
- Redis is used for ephemeral state such as purchase hold cache and verification locks, not as the primary record of business data.
- RabbitMQ carries delayed hold expiry and transfer notification work so those flows are not tied to synchronous request latency.

## How to Start Backend: Complete Guide

This guide assumes you're starting from scratch with nothing installed. Choose your setup path based on your needs:

- **Option 1: Local Development Only** - Run backend on your laptop with local port-forwarding (no internet exposure)
- **Option 2: Public Access via Cloudflare** - Expose your local backend to the internet for remote testing or frontend collaboration

### Prerequisites Installation

You need these tools installed before starting. Follow the steps for your operating system.

#### 1. Install Docker Desktop

Docker Desktop provides the container runtime that Minikube uses.

**Windows:**
1. Download Docker Desktop from https://www.docker.com/products/docker-desktop
2. Run the installer and follow the prompts
3. Restart your computer when prompted
4. Launch Docker Desktop from the Start menu
5. Wait for Docker to fully start (the whale icon in the system tray will stop animating)

**Verify installation:**
```powershell
docker --version
docker info
```

**Troubleshooting:**
- If `docker info` fails with "error during connect", Docker Desktop is not running. Start it from the Start menu.
- If you see "WSL 2 installation is incomplete", follow the prompts to install WSL 2 and restart.

#### 2. Install Minikube

Minikube runs a local Kubernetes cluster on your machine.

**Windows:**
1. Download the latest Minikube installer from https://minikube.sigs.k8s.io/docs/start/
2. Run the installer as Administrator
3. Add Minikube to your PATH if the installer didn't do it automatically

**Verify installation:**
```powershell
minikube version
```

**Troubleshooting:**
- If `minikube` command is not found, add `C:\Program Files\Minikube` to your PATH environment variable and restart PowerShell.

#### 3. Install kubectl

kubectl is the Kubernetes command-line tool.

**Windows:**
1. Download kubectl from https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/
2. Place `kubectl.exe` in a directory that's in your PATH (e.g., `C:\Program Files\kubectl\`)
3. Restart PowerShell

**Verify installation:**
```powershell
kubectl version --client
```

**Troubleshooting:**
- If `kubectl` command is not found, ensure the directory containing `kubectl.exe` is in your PATH.

#### 4. Install Node.js and Newman

Newman is the CLI test runner for Postman collections. It requires Node.js.

**Windows:**
1. Download Node.js LTS from https://nodejs.org/
2. Run the installer and follow the prompts (accept all defaults)
3. Restart PowerShell
4. Install Newman globally:
```powershell
npm install -g newman
```

**Verify installation:**
```powershell
node --version
npm --version
newman --version
```

**Troubleshooting:**
- If `npm` command is not found after installing Node.js, restart your computer.
- If Newman installation fails with permission errors, run PowerShell as Administrator and retry.

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

**Troubleshooting:**
- If your machine has less than 16GB RAM, reduce memory to 8192 (8GB) but expect slower performance.
- If Minikube fails to start later, try increasing these values.

#### 2. Obtain the Secrets File

The backend requires a secrets file that contains API keys, database passwords, and other sensitive configuration.

**Ask your backend maintainer for:**
- `k8s/base/secrets.local.yaml`

**Place it at:**
```
ticketremaster-b/k8s/base/secrets.local.yaml
```

This file is gitignored and must be obtained from the team. It typically contains:
- Cloudflare tunnel token (required for Option 2 only)
- OutSystems API keys for credit operations
- Database passwords
- Stripe and OTP wrapper secrets

**Troubleshooting:**
- If you don't have this file, the startup script will fail immediately with a clear error message.
- If you have an outdated version, you may see `400` errors during registration or `401` errors during login.

#### 3. Start Minikube

Start your local Kubernetes cluster:

```powershell
minikube start
```

This will take 2-5 minutes on first run. Minikube will:
- Download the Kubernetes ISO image
- Create a virtual machine
- Configure kubectl to point to the cluster

**Verify Minikube is running:**
```powershell
minikube status
kubectl get nodes
```

You should see one node in "Ready" state.

**Troubleshooting:**
- If `minikube start` fails with "Exiting due to HOST_VIRT_UNAVAILABLE", enable virtualization in your BIOS.
- If it fails with memory errors, reduce the memory allocation in step 1.
- If it hangs, try `minikube delete` and then `minikube start` again.

### Option 1: Local Development Setup (Localhost Only)

This setup runs the backend on your machine and exposes it only on `http://localhost:8000`. No internet exposure.

#### Quick Start

From the `ticketremaster-b` directory, double-click:
```
start-backend.bat
```

When prompted, choose **Option 1: Localhost only**.

The script will:
1. Check for the secrets file
2. Start Docker Desktop if needed
3. Start Minikube if needed
4. Build Docker images for all services (first run takes 10-15 minutes)
5. Apply Kubernetes manifests
6. Wait for all pods to be ready
7. Run database seed jobs
8. Open a port-forward to Kong on `http://localhost:8000`
9. Run Newman smoke tests to verify everything works

**Alternative: PowerShell command**
```powershell
.\scripts\start_k8s.ps1
```

#### What to Expect

**First run (with no images built):**
- Total time: 15-20 minutes
- Most time is spent building Docker images

**Subsequent runs (images already built):**
- Total time: 3-5 minutes
- Startup is much faster

**Success indicators:**
- You'll see "Backend startup completed successfully"
- A minimized PowerShell window will stay open (this is the port-forward, don't close it)
- Newman tests will show green checkmarks
- Kong is available at `http://localhost:8000`

#### Verify It's Working

Test the gateway:
```powershell
Invoke-WebRequest http://localhost:8000/events
```

You should see JSON with event data.

**Configure your frontend:**
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_KONG_API_KEY=tk_front_123456789
```

#### Troubleshooting

**Problem: "secrets.local.yaml not found"**
- Solution: Obtain the secrets file from your backend maintainer and place it at `k8s/base/secrets.local.yaml`.

**Problem: Docker Desktop fails to start**
- Solution: Start Docker Desktop manually from the Start menu, wait for it to fully start, then run `start-backend.bat` again.

**Problem: Minikube fails to start**
- Solution: Try `minikube delete` followed by `minikube start`. If it still fails, check that virtualization is enabled in your BIOS.

**Problem: Build fails with "no space left on device"**
- Solution: Clean up Docker: `docker system prune -a --volumes` and retry.

**Problem: Pods stuck in "ImagePullBackOff"**
- Solution: Rebuild and reload images:
```powershell
.\scripts\build_k8s_images.ps1
```

**Problem: Register returns 400, then login returns 401**
- This means services weren't ready when seed jobs ran.
- Solution: Wait for all pods to be ready, then re-run seed jobs:
```powershell
.\scripts\rerun_k8s_seeds.ps1
```

**Problem: Port 8000 is already in use**
- The startup script will automatically find an available port and tell you which one it's using.
- Update your frontend config to use the new port.

**Problem: Port-forward window closes unexpectedly**
- Solution: Restart it manually:
```powershell
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
```

### Option 2: Public Access Setup (Cloudflare Tunnel)

This setup exposes your local backend to the internet via Cloudflare Tunnel at `https://ticketremasterapi.hong-yi.me`. Useful for:
- Remote testing
- Sharing with frontend developers who don't want to run the backend
- Mobile device testing

#### Prerequisites

In addition to the standard prerequisites, you need:
- A `secrets.local.yaml` file that contains a valid `CLOUDFLARE_TUNNEL_TOKEN`
- The token must be configured to route to the Kong service

Ask your backend maintainer for the Cloudflare tunnel token if you don't have it.

#### Quick Start

From the `ticketremaster-b` directory, double-click:
```
start-backend.bat
```

When prompted, choose:
- **Option 2: Cloudflare only** - No local port-forward, only public URL
- **Option 3: Both** - Local port-forward AND public URL (recommended for development)

The script will:
1. Do everything from Option 1
2. Deploy the Cloudflare tunnel connector
3. Wait for the tunnel to establish
4. Run Newman smoke tests against the public URL

**Alternative: PowerShell command**
```powershell
.\scripts\start_k8s.ps1 -RunPublicTests
```

#### What to Expect

**First run:**
- Total time: 15-25 minutes
- Includes image building + tunnel connection time

**Subsequent runs:**
- Total time: 4-6 minutes

**Success indicators:**
- Newman tests pass for both localhost (if Option 3) and public URL
- Public gateway is accessible at `https://ticketremasterapi.hong-yi.me`

#### Verify It's Working

Test the public gateway:
```powershell
Invoke-WebRequest https://ticketremasterapi.hong-yi.me/events
```

You should see JSON with event data.

**Configure your frontend for public access:**
```env
VITE_API_BASE_URL=https://ticketremasterapi.hong-yi.me
VITE_KONG_API_KEY=tk_front_123456789
```

#### Troubleshooting

**Problem: Cloudflare tunnel fails to connect**
- Check the tunnel token in `secrets.local.yaml` is valid and not expired
- Check cloudflared logs:
```powershell
kubectl logs deployment/cloudflared -n ticketremaster-edge --tail=100
```
- Solution: Restart the cloudflared deployment:
```powershell
kubectl rollout restart deployment/cloudflared -n ticketremaster-edge
```

**Problem: Public URL returns 502 Bad Gateway**
- This means the tunnel is up but Kong is not ready yet.
- Solution: Wait 1-2 minutes and try again. Check Kong logs:
```powershell
kubectl logs deployment/kong -n ticketremaster-edge --tail=100
```

**Problem: Public URL works intermittently**
- The tunnel connector may be restarting.
- Check cloudflared pod status:
```powershell
kubectl get pods -n ticketremaster-edge
```
- If cloudflared pod is restarting, check its logs for errors.

**Problem: Public tests fail but localhost tests pass**
- The tunnel may not be fully established yet.
- Solution: Wait 2-3 minutes for the tunnel to stabilize, then run tests again:
```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli
```

### Manual Control (Advanced)

If you prefer full control over the startup process:

#### Start the cluster
```powershell
minikube start
```

#### Build images (first time or after code changes)
```powershell
.\scripts\build_k8s_images.ps1
```

#### Apply manifests
```powershell
kubectl apply -k k8s/base
```

#### Wait for everything to be ready
```powershell
# Wait for data plane
kubectl rollout status statefulset/redis -n ticketremaster-data --timeout=300s
kubectl rollout status statefulset/rabbitmq -n ticketremaster-data --timeout=300s

# Wait for core services
kubectl rollout status deployment/auth-orchestrator -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/user-service -n ticketremaster-core --timeout=300s

# Wait for edge
kubectl rollout status deployment/kong -n ticketremaster-edge --timeout=300s

# Wait for seed jobs
kubectl wait --for=condition=complete job --all -n ticketremaster-core --timeout=600s
```

#### Open port-forward
```powershell
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
```

Keep this terminal open while using the backend.

#### Run smoke tests
```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli
```

### Checking Cluster Status

#### View all pods
```powershell
kubectl get pods -n ticketremaster-edge
kubectl get pods -n ticketremaster-core
kubectl get pods -n ticketremaster-data
```

All pods should show "Running" status.

#### View seed jobs
```powershell
kubectl get jobs -n ticketremaster-core
```

All jobs should show "1/1" completions.

#### View logs for a specific service
```powershell
kubectl logs deployment/auth-orchestrator -n ticketremaster-core --tail=100
kubectl logs deployment/user-service -n ticketremaster-core --tail=100
```

#### Access RabbitMQ management UI
```powershell
kubectl port-forward -n ticketremaster-data service/rabbitmq 15672:15672
```

Then open `http://localhost:15672` in your browser.
- Username: `guest`
- Password: `guest`

### Stopping the Backend

#### Stop port-forward
Close the PowerShell window running the port-forward, or press `Ctrl+C`.

#### Stop Minikube (preserves data)
```powershell
minikube stop
```

#### Delete Minikube (removes all data)
```powershell
minikube delete
```

Use `minikube delete` if you want a completely fresh start or if you're having persistent issues.

### Common Issues and Solutions

#### Issue: Everything was working, now nothing works after restart

**Cause:** Minikube's persistent volumes were wiped but seed jobs don't re-run automatically.

**Solution:** Re-run seed jobs:
```powershell
.\scripts\rerun_k8s_seeds.ps1
```

Or delete and reapply the jobs:
```powershell
kubectl delete job seed-venues seed-events seed-seats seed-seat-inventory seed-users -n ticketremaster-core
kubectl apply -k k8s/base
kubectl wait --for=condition=complete job --all -n ticketremaster-core --timeout=600s
```

#### Issue: Services are crashing with database connection errors

**Cause:** Database passwords in `secrets.local.yaml` don't match what the databases expect.

**Solution:** Get the latest `secrets.local.yaml` from your backend maintainer and reapply:
```powershell
kubectl delete -k k8s/base
kubectl apply -k k8s/base
```

#### Issue: Out of disk space

**Cause:** Docker images and Minikube volumes accumulate over time.

**Solution:** Clean up Docker:
```powershell
docker system prune -a --volumes
minikube delete
minikube start
```

Then rebuild:
```powershell
.\scripts\build_k8s_images.ps1
```

#### Issue: Minikube won't start after Windows update

**Cause:** Windows updates sometimes break virtualization or Docker.

**Solution:**
1. Restart Docker Desktop
2. Try `minikube delete` then `minikube start`
3. If still failing, reinstall Minikube

#### Issue: Newman tests fail with timeout errors

**Cause:** Services are still starting up or are overloaded.

**Solution:** Wait 1-2 minutes and run tests again:
```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli
```

## Public and Local Surfaces

- **Local gateway:** `http://localhost:8000` (when port-forward is active)
- **Public gateway:** `https://ticketremasterapi.hong-yi.me` (when Cloudflare tunnel is configured)
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

1. Rebuild images:
```powershell
.\scripts\build_k8s_images.ps1
```

2. Restart affected deployments:
```powershell
# Restart specific service
kubectl rollout restart deployment/user-service -n ticketremaster-core

# Or restart all core services
kubectl rollout restart deployment -n ticketremaster-core
```

3. Wait for rollout to complete:
```powershell
kubectl rollout status deployment/user-service -n ticketremaster-core
```

The startup script automatically detects code changes and rebuilds images when needed.

### Running Tests

The repository includes Newman smoke tests that verify the gateway and all major workflows.

**Run localhost tests:**
```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli
```

**Run public tests:**
```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli
```

### Viewing Service Documentation

Each service exposes Swagger/Flasgger documentation at its `/apidocs` endpoint. To access it:

1. Port-forward to the service:
```powershell
kubectl port-forward -n ticketremaster-core deployment/user-service 5000:5000
```

2. Open `http://localhost:5000/apidocs` in your browser

## For Frontend Developers

If you only need to consume the backend and don't want to run it locally:

**Use the shared public backend:**
```env
VITE_API_BASE_URL=https://ticketremasterapi.hong-yi.me
VITE_KONG_API_KEY=tk_front_123456789
```

No installation required. The backend maintainer keeps this instance running and up-to-date.

**Note:** The public backend is shared among the team. Don't use it for destructive testing or load testing.
