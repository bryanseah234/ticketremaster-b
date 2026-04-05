@echo off
title TicketRemaster Backend Startup
echo ============================================
echo  TicketRemaster Backend - Starting up...
echo ============================================
echo.

cd /d "%~dp0"

:: ── Check secrets file exists ─────────────────────────────────────
echo [1/6] Checking secrets file...
if not exist "k8s\base\secrets.local.yaml" (
    echo.
    echo ERROR: k8s\base\secrets.local.yaml not found.
    echo Ask the backend maintainer for this file and place it at:
    echo   %~dp0k8s\base\secrets.local.yaml
    echo.
    pause
    exit /b 1
)
echo secrets.local.yaml found.
echo.

:: ── Detect if Cloudflare tunnel token is configured ───────────────
set HAS_CLOUDFLARE=0
findstr /i "CLOUDFLARE_TUNNEL_TOKEN" k8s\base\secrets.local.yaml >nul 2>&1
if %errorlevel% equ 0 (
    :: Check it's not empty or placeholder
    findstr /i "CLOUDFLARE_TUNNEL_TOKEN: eyJ" k8s\base\secrets.local.yaml >nul 2>&1
    if %errorlevel% equ 0 set HAS_CLOUDFLARE=1
)

if "%HAS_CLOUDFLARE%"=="1" (
    echo Cloudflare tunnel token detected.
    echo Public URL will be available at: https://ticketremasterapi.hong-yi.me
) else (
    echo No Cloudflare tunnel token found in secrets.local.yaml.
    echo You will use localhost:8000 via port-forward only.
    echo To get a public URL, ask the backend maintainer for the tunnel token.
)
echo.

:: ── Check Docker Desktop is running ──────────────────────────────
echo [2/6] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker Desktop is not running. Starting it...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo Waiting for Docker to start (30 seconds)...
    timeout /t 30 /nobreak >nul
    docker info >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Docker Desktop failed to start. Please start it manually and re-run.
        pause
        exit /b 1
    )
)
echo Docker Desktop is running.
echo.

:: ── Check Minikube status ─────────────────────────────────────────
echo [3/6] Checking Minikube...
minikube status >nul 2>&1
if %errorlevel% neq 0 (
    echo Starting Minikube...
    minikube start
    if %errorlevel% neq 0 (
        echo ERROR: Minikube failed to start.
        pause
        exit /b 1
    )
) else (
    echo Minikube is already running.
)
echo.

:: ── Apply manifests ───────────────────────────────────────────────
echo [4/6] Applying k8s manifests...
kubectl apply -k k8s/base
if %errorlevel% neq 0 (
    echo ERROR: kubectl apply failed.
    pause
    exit /b 1
)
echo.
:: ── Wait for pods ─────────────────────────────────────────────────
echo [5/6] Waiting for pods to be ready (up to 3 minutes)...
kubectl wait --for=condition=ready pod -l app=kong -n ticketremaster-edge --timeout=180s >nul 2>&1
kubectl wait --for=condition=ready pod -l app=auth-orchestrator -n ticketremaster-core --timeout=180s >nul 2>&1
kubectl wait --for=condition=ready pod -l app=event-orchestrator -n ticketremaster-core --timeout=180s >nul 2>&1
echo Pods are ready.
echo.

:: ── Start port-forward ────────────────────────────────────────────
echo [6/6] Starting Kong port-forward on localhost:8000...
start "Kong Port-Forward (keep open)" cmd /k "kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80"
timeout /t 3 /nobreak >nul
echo.

:: ── Summary ───────────────────────────────────────────────────────
echo ============================================
echo  Backend is ready!
echo.
echo  Local:  http://localhost:8000
if "%HAS_CLOUDFLARE%"=="1" (
    echo  Public: https://ticketremasterapi.hong-yi.me
) else (
    echo  Public: NOT AVAILABLE (no Cloudflare token)
    echo          Use localhost:8000 for all development.
)
echo.
echo  Keep the "Kong Port-Forward" window open for localhost to work.
echo ============================================
echo.
echo Press any key to run gateway tests, or close this window to skip.
pause >nul

:: ── Run tests ─────────────────────────────────────────────────────
echo.
if "%HAS_CLOUDFLARE%"=="1" (
    echo Running tests against PUBLIC URL...
    newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli
    echo.
)

echo Running tests against LOCALHOST...
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli

echo.
echo Done! Press any key to close.
pause >nul
