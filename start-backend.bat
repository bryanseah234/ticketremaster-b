@echo off
setlocal EnableExtensions

title TicketRemaster Backend Startup
echo ============================================
echo  TicketRemaster Backend - Starting up...
echo ============================================
echo.

cd /d "%~dp0"

set "SECRETS_FILE=k8s\base\secrets.local.yaml"
set "START_SCRIPT=scripts\start_k8s.ps1"
set "HAS_CF_TOKEN=0"
set "RUN_PUBLIC_TESTS=0"
set "SKIP_PORT_FORWARD=0"

echo [1/5] Checking required repo files...
call :require_file "%SECRETS_FILE%" "Kubernetes secrets file"
if errorlevel 1 goto fail
call :require_file "%START_SCRIPT%" "Kubernetes startup script"
if errorlevel 1 goto fail
echo Required repo files found.

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
call :require_command docker "Docker CLI"
if errorlevel 1 goto fail
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
call :require_command minikube "Minikube CLI"
if errorlevel 1 goto fail
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
call :require_command powershell "Windows PowerShell"
if errorlevel 1 goto fail
set "PS_ARGS="
if "%RUN_PUBLIC_TESTS%"=="1" set "PS_ARGS=%PS_ARGS% -RunPublicTests"
if "%SKIP_PORT_FORWARD%"=="1" set "PS_ARGS=%PS_ARGS% -SkipPortForward"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0%START_SCRIPT%"%PS_ARGS%

if errorlevel 1 (
    echo.
    echo Backend startup failed. Review the output above.
    goto fail
)

echo.
echo Backend startup completed successfully.
echo Press any key to close.
pause >nul
exit /b 0

:fail
echo.
pause
exit /b 1

:require_file
if exist "%~1" exit /b 0
echo ERROR: %~2 not found.
echo Expected path: %~dp0%~1
exit /b 1

:require_command
where "%~1" >nul 2>&1
if %errorlevel% equ 0 exit /b 0
echo ERROR: %~2 was not found in PATH.
echo Install "%~1" and try again.
exit /b 1
