#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Full Minikube startup script for TicketRemaster backend.
    Run this after every `minikube start` to get everything healthy.

.USAGE
    cd ticketremaster-b
    .\scripts\start_k8s.ps1

    Optional flags:
    -SkipImageLoad   Skip loading Docker images (use if images already loaded)
    -SkipPortForward Skip starting the port-forward (use if you only need public URL)
    -PublicOnly      Only test the public URL (skip localhost tests)
#>
param(
    [switch]$SkipImageLoad,
    [switch]$SkipPortForward,
    [switch]$PublicOnly
)

$ErrorActionPreference = "Stop"
$Tag = "local-k8s-20260329"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    [!!] $msg" -ForegroundColor Yellow }

# ── 1. Check prerequisites ──────────────────────────────────────────────────
Write-Step "Checking prerequisites"
foreach ($cmd in @("kubectl","minikube","newman")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Error "$cmd not found. Install it first."
    }
    Write-OK "$cmd found"
}

# ── 2. Check Minikube is running ─────────────────────────────────────────────
Write-Step "Checking Minikube"
$nodes = kubectl get nodes --request-timeout=10s 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Minikube is not running or API server is unreachable. Run: minikube start"
}
Write-OK "Minikube is up"

# ── 3. Load images if needed ─────────────────────────────────────────────────
if (-not $SkipImageLoad) {
    Write-Step "Checking if images are loaded in Minikube"
    $loaded = minikube image list 2>&1 | Select-String "ticketremaster"
    if (-not $loaded) {
        Write-Warn "Images not found in Minikube. Loading now (this takes ~10 mins)..."
        $images = @(
            "user-service","venue-service","seat-service","event-service",
            "seat-inventory-service","ticket-service","ticket-log-service",
            "marketplace-service","transfer-service","credit-transaction-service",
            "stripe-wrapper","otp-wrapper","auth-orchestrator","event-orchestrator",
            "credit-orchestrator","ticket-purchase-orchestrator","qr-orchestrator",
            "marketplace-orchestrator","transfer-orchestrator","ticket-verification-orchestrator"
        )
        # Check Docker images exist first
        $dockerImages = docker images --format "{{.Repository}}:{{.Tag}}" 2>&1 | Select-String "ticketremaster"
        if (-not $dockerImages) {
            Write-Warn "Docker images not built. Building now..."
            & "$PSScriptRoot\build_k8s_images.ps1" -Tag $Tag
        }
        foreach ($img in $images) {
            Write-Host "    Loading $img..."
            minikube image load "ticketremaster/${img}:${Tag}"
        }
        Write-OK "All images loaded"
    } else {
        Write-OK "Images already in Minikube"
    }
}

# ── 4. Apply manifests ───────────────────────────────────────────────────────
Write-Step "Applying k8s manifests"
kubectl apply -k k8s/base --request-timeout=30s 2>&1 | Out-Null
Write-OK "Manifests applied"

# ── 5. Wait for data plane ───────────────────────────────────────────────────
Write-Step "Waiting for databases and RabbitMQ (up to 3 min)"
$dataPods = @("user-service-db","event-service-db","rabbitmq","redis")
foreach ($pod in $dataPods) {
    Write-Host "    Waiting for $pod..."
    kubectl wait --for=condition=ready pod -l "app=$pod" -n ticketremaster-data --timeout=180s 2>&1 | Out-Null
}
Write-OK "Data plane ready"

# ── 6. Wait for core services ────────────────────────────────────────────────
Write-Step "Waiting for core services (up to 3 min)"
$corePods = @("auth-orchestrator","event-orchestrator","kong")
foreach ($pod in $corePods) {
    $ns = if ($pod -eq "kong") { "ticketremaster-edge" } else { "ticketremaster-core" }
    Write-Host "    Waiting for $pod..."
    kubectl wait --for=condition=ready pod -l "app=$pod" -n $ns --timeout=180s 2>&1 | Out-Null
}
Write-OK "Core services ready"

# ── 7. Run DB migrations ─────────────────────────────────────────────────────
Write-Step "Running DB migrations"
kubectl exec -n ticketremaster-core deployment/user-service -- flask db upgrade 2>&1 | Out-Null
Write-OK "Migrations done"

# ── 8. Port-forward Kong ─────────────────────────────────────────────────────
if (-not $SkipPortForward -and -not $PublicOnly) {
    Write-Step "Starting Kong port-forward on localhost:8000"
    Start-Process powershell -ArgumentList "-NoExit -Command kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80" -WindowStyle Minimized
    Start-Sleep -Seconds 3
    Write-OK "Port-forward started (minimized window — keep it open)"
}

# ── 9. Run tests ─────────────────────────────────────────────────────────────
Write-Step "Running gateway tests"

if (-not $PublicOnly) {
    Write-Host "`n--- Localhost (port-forward) ---" -ForegroundColor White
    newman run postman/TicketRemaster.gateway.postman_collection.json `
        -e postman/TicketRemaster.gateway-localhost.postman_environment.json `
        --reporters cli
}

Write-Host "`n--- Public URL (Cloudflare) ---" -ForegroundColor White
newman run postman/TicketRemaster.gateway.postman_collection.json `
    -e postman/TicketRemaster.gateway-public.postman_environment.json `
    --reporters cli

Write-Step "Done!"
