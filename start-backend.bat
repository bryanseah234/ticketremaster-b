@echo off
setlocal EnableExtensions

title TicketRemaster Backend Startup
echo ============================================
echo  TicketRemaster Backend - Starting up...
echo ============================================
echo.

cd /d "%~dp0"

set "SECRETS_FILE=k8s\base\secrets.local.yaml"
set "RUN_PUBLIC_TESTS=0"

echo [1/4] Checking secrets file...
if not exist "%SECRETS_FILE%" (
    echo.
    echo ERROR: %SECRETS_FILE% not found.
    echo Ask the backend maintainer for this file and place it at:
    echo   %~dp0%SECRETS_FILE%
    echo.
    pause
    exit /b 1
)
echo secrets.local.yaml found.

findstr /i /r /c:"CLOUDFLARE_TUNNEL_TOKEN: .*[A-Za-z0-9]" "%SECRETS_FILE%" >nul 2>&1
if %errorlevel% equ 0 (
    set "RUN_PUBLIC_TESTS=1"
    echo Cloudflare tunnel token detected.
    echo Public smoke tests will run against https://ticketremasterapi.hong-yi.me after the tunnel reconnects.
) else (
    echo No Cloudflare tunnel token detected.
    echo Localhost smoke tests only.
)
echo.

echo [2/4] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker Desktop is not running. Starting it...
    if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
        start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        echo Waiting 30 seconds for Docker to start...
        timeout /t 30 /nobreak >nul
        docker info >nul 2>&1
    )
    if %errorlevel% neq 0 (
        echo ERROR: Docker Desktop failed to start. Start it manually and run start-backend.bat again.
        pause
        exit /b 1
    )
)
echo Docker Desktop is running.
echo.

echo [3/4] Checking Minikube...
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

echo [4/4] Applying manifests, waiting for workloads, starting port-forward, and running smoke tests...
if "%RUN_PUBLIC_TESTS%"=="1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_k8s.ps1" -RunPublicTests
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_k8s.ps1"
)

if errorlevel 1 (
    echo.
    echo Backend startup failed. Review the output above.
    pause
    exit /b 1
)

echo.
echo Backend startup completed successfully.
echo Press any key to close.
pause >nul
