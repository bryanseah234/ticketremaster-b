# Local Development Setup

This is the current local development guide for the Kubernetes-backed backend in `ticketremaster-b`.

## Fastest path

### I maintain the backend and run Minikube

Double-click `start-backend.bat` in the repo root.

It now covers the full happy path:

- checks `k8s/base/secrets.local.yaml`
- starts Docker Desktop if needed
- starts Minikube if needed
- applies `k8s/base`
- waits for data StatefulSets, core Deployments, edge Deployments, and seed Jobs
- opens a Kong port-forward on `localhost:8000`
- runs the localhost Newman gateway smoke suite
- runs the public Newman smoke suite too when `CLOUDFLARE_TUNNEL_TOKEN` is configured

### I want the same flow from PowerShell

```powershell
.\scripts\start_k8s.ps1
```

Public smoke suite too:

```powershell
.\scripts\start_k8s.ps1 -RunPublicTests
```

### I only consume the shared backend from the frontend

You do not need Minikube. Point the frontend at:

```env
VITE_API_BASE_URL=https://ticketremasterapi.hong-yi.me
VITE_KONG_API_KEY=tk_front_123456789
```

The backend maintainer still needs their local cluster and Cloudflare tunnel to be healthy.

## Prerequisites

| Tool | Notes |
| --- | --- |
| Docker Desktop | Required for Minikube image builds and runtime |
| Minikube | Local Kubernetes cluster |
| kubectl | Cluster access |
| Newman | Gateway smoke suite runner |
| Node.js | Needed for `newman` and the frontend repo |

## Required local secret file

`k8s/base/secrets.local.yaml` is required and is intentionally gitignored.

It typically contains:

- Cloudflare tunnel token for the edge namespace
- OutSystems API key for credit operations
- database passwords and shared runtime secrets
- Stripe and OTP wrapper secrets

If this file is missing or stale, startup may succeed only partially. A common symptom is:

- `POST /auth/register` returning `400`
- followed by `POST /auth/login` returning `401`

That usually means auth came up before one of its downstream services, or the secret material is outdated.

## First-time machine setup

### 1. Allocate enough Minikube memory

```powershell
minikube config set memory 12288
minikube config set cpus 4
```

If you use WSL on Windows, also set:

```ini
[wsl2]
memory=12GB
```

Then run:

```powershell
wsl --shutdown
```

### 2. Build the local images

Run this the first time, or after `minikube delete`, or after you have changed backend code that must be rebuilt:

```powershell
.\scripts\build_k8s_images.ps1
```

The current default local image tag is `local-k8s-20260329`, which is also the tag referenced by `k8s/base`.

### 3. Apply the stack

```powershell
kubectl apply -k k8s/base
```

### 4. Wait for the stack properly

Do not rely on a fixed sleep. Wait for real conditions:

```powershell
kubectl rollout status statefulset/redis -n ticketremaster-data --timeout=300s
kubectl rollout status statefulset/rabbitmq -n ticketremaster-data --timeout=300s
kubectl rollout status deployment/auth-orchestrator -n ticketremaster-core --timeout=300s
kubectl rollout status deployment/kong -n ticketremaster-edge --timeout=300s
kubectl wait --for=condition=complete job --all -n ticketremaster-core --timeout=600s
```

The maintained startup scripts perform this waiting for you.

### 5. Port-forward Kong

```powershell
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
```

Keep that terminal open while using `http://localhost:8000`.

## Manual maintainer flow

Use this when you want full control rather than the launcher:

```powershell
minikube start
kubectl apply -k k8s/base
kubectl wait --for=condition=available deployment --all -n ticketremaster-core --timeout=300s
kubectl wait --for=condition=complete job --all -n ticketremaster-core --timeout=600s
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli
```

## Frontend setup

For local backend usage:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_KONG_API_KEY=tk_front_123456789
```

For the shared public backend:

```env
VITE_API_BASE_URL=https://ticketremasterapi.hong-yi.me
VITE_KONG_API_KEY=tk_front_123456789
```

## Smoke verification

### Localhost

```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli
```

### Public Cloudflare route

```powershell
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli
```

### Quick cluster checks

```powershell
kubectl get pods -n ticketremaster-edge
kubectl get pods -n ticketremaster-core
kubectl get pods -n ticketremaster-data
kubectl get jobs -n ticketremaster-core
```

## Troubleshooting

### `start-backend.bat` fails at Docker check with `... was unexpected at this time.`

That was a Windows batch parsing bug in the old launcher. The current launcher delegates to PowerShell after lightweight checks and no longer uses the broken branch structure.

### Register returns `400`, then login and other protected routes return `401`

Treat this as a readiness chain, not as many unrelated auth bugs.

Check:

```powershell
kubectl get pods -n ticketremaster-core
kubectl get jobs -n ticketremaster-core
kubectl logs deployment/auth-orchestrator -n ticketremaster-core --tail=100
kubectl logs deployment/user-service -n ticketremaster-core --tail=100
```

Typical causes:

- user-service was not ready when auth tried to create the test account
- seed jobs had not completed yet
- secrets were outdated, especially OutSystems or database secrets

### Public URL works intermittently

Cloudflare Tunnel is still a single-connector edge. If the public URL is unstable:

```powershell
kubectl logs deployment/cloudflared -n ticketremaster-edge --tail=100
kubectl logs deployment/kong -n ticketremaster-edge --tail=100
```

Also confirm the public endpoint itself:

```powershell
Invoke-WebRequest https://ticketremasterapi.hong-yi.me/events
```

### `ImagePullBackOff` after `minikube delete`

Rebuild and reload local images:

```powershell
.\scripts\build_k8s_images.ps1
```

The maintained startup script will load missing images into Minikube automatically.

### Port-forward drops

Restart it:

```powershell
kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80
```

### RabbitMQ management UI

To inspect queues locally:

```powershell
kubectl port-forward -n ticketremaster-data service/rabbitmq 15672:15672
```

Then open `http://localhost:15672`.
