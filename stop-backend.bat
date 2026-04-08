@echo off
setlocal EnableExtensions

title TicketRemaster Backend Shutdown
echo ============================================
echo  TicketRemaster Backend - Shutting down...
echo ============================================
echo.

set "EXIT_CODE=0"
cd /d "%~dp0"

echo [1/2] Stopping kubectl port-forwards...
taskkill /F /FI "WINDOWTITLE eq kubectl*" >nul 2>&1
taskkill /F /IM kubectl.exe >nul 2>&1
if exist ".local-gateway-url" del /q ".local-gateway-url" >nul 2>&1
echo Done.
echo.

echo [2/2] Stopping Minikube...
where minikube >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Minikube CLI is not installed or not in PATH. Skipping stop command.
    set "EXIT_CODE=1"
) else (
    minikube stop
    if %errorlevel% neq 0 (
        echo WARNING: Minikube stop returned an error. It may already be stopped.
        set "EXIT_CODE=1"
    ) else (
        echo Minikube stopped.
    )
)
echo.

echo Backend stopped. Safe to shut down your machine.
pause >nul
exit /b %EXIT_CODE%
