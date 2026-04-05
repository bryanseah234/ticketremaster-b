@echo off
title TicketRemaster Backend Startup
echo ============================================
echo  TicketRemaster Backend - Starting up...
echo ============================================
echo.

:: ── Check Docker Desktop is running ──────────────────────────────
echo [1/5] Checking Docker Desktop...
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
echo [2/5] Checking Minikube...
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
echo [3/5] Applying k8s manifests...
cd /d "%~dp0"
kubectl apply -k k8s/base
if %errorlevel% neq 0 (
    echo ERROR: kubectl apply failed. Check your secrets.local.yaml exists.
    pause
    exit /b 1
)
echo.

:: ── Wait for pods ─────────────────────────────────────────────────
echo [4/5] Waiting for pods to be ready (up to 3 minutes)...
kubectl wait --for=condition=ready pod -l app=kong -n ticketremaster-edge --timeout=180s >nul 2>&1
kubectl wait --for=condition=ready pod -l app=auth-orchestrator -n ticketremaster-core --timeout=180s >nul 2>&1
kubectl wait --for=condition=ready pod -l app=event-orchestrator -n ticketremaster-core --timeout=180s >nul 2>&1
echo Pods are ready.
echo.

:: ── Start port-forward in new window ─────────────────────────────
echo [5/5] Starting Kong port-forward on localhost:8000...
start "Kong Port-Forward" cmd /k "kubectl port-forward -n ticketremaster-edge service/kong-proxy 8000:80"
timeout /t 3 /nobreak >nul
echo.

echo ============================================
echo  Backend is ready!
echo  Local:  http://localhost:8000
echo  Public: https://ticketremasterapi.hong-yi.me
echo ============================================
echo.
echo The port-forward window must stay open for localhost to work.
echo Press any key to run gateway tests, or close this window to skip.
pause >nul

:: ── Run tests ─────────────────────────────────────────────────────
echo.
echo Running gateway tests (public URL)...
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli

echo.
echo Running gateway tests (localhost)...
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli

echo.
echo Done! Press any key to close.
pause >nul
