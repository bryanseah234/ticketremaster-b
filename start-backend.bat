@echo off
setlocal EnableExtensions

title TicketRemaster Backend Startup
echo ============================================
echo  TicketRemaster Backend - Starting up...
echo ============================================
echo.

cd /d "%~dp0"

set "SECRETS_FILE=k8s\base\secrets.local.yaml"
set "HAS_CF_TOKEN=0"
set "RUN_PUBLIC_TESTS=0"
set "SKIP_PORT_FORWARD=0"

echo [1/5] Checking secrets file...
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
    set "HAS_CF_TOKEN=1"
)
echo.

echo [2/5] Startup mode selection
echo ----------------------------------------
echo   1. Localhost only   (port-forward, no Cloudflare tunnel)
echo   2. Cloudflare only  (tunnel to internet, no local port-forward)
echo   3. Both             (port-forward + Cloudflare tunnel)
echo ----------------------------------------
if "%HAS_CF_TOKEN%"=="0" (
    echo   NOTE: No Cloudflare tunnel token found - options 2 and 3 will skip the tunnel.
)
echo.
set /p "MODE_CHOICE=Enter choice [1/2/3] (default: 1): "
if "%MODE_CHOICE%"=="" set "MODE_CHOICE=1"

if "%MODE_CHOICE%"=="1" (
    echo Mode: Localhost only
    set "SKIP_PORT_FORWARD=0"
    set "RUN_PUBLIC_TESTS=0"
) else if "%MODE_CHOICE%"=="2" (
    echo Mode: Cloudflare only
    set "SKIP_PORT_FORWARD=1"
    set "RUN_PUBLIC_TESTS=1"
) else if "%MODE_CHOICE%"=="3" (
    echo Mode: Both
    set "SKIP_PORT_FORWARD=0"
    set "RUN_PUBLIC_TESTS=1"
) else (
    echo Invalid choice. Defaulting to localhost only.
    set "SKIP_PORT_FORWARD=0"
    set "RUN_PUBLIC_TESTS=0"
)
echo.

echo [3/5] Checking Docker Desktop...
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

echo [4/5] Checking Minikube...
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

echo [5/5] Applying manifests, waiting for workloads, and starting selected services...
set "PS_ARGS="
if "%RUN_PUBLIC_TESTS%"=="1" set "PS_ARGS=%PS_ARGS% -RunPublicTests"
if "%SKIP_PORT_FORWARD%"=="1" set "PS_ARGS=%PS_ARGS% -SkipPortForward"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_k8s.ps1"%PS_ARGS%

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
