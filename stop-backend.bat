@echo off
setlocal EnableExtensions

title TicketRemaster Backend Shutdown
echo ============================================
echo  TicketRemaster Backend - Shutting down...
echo ============================================
echo.

echo [1/2] Stopping kubectl port-forwards...
taskkill /F /FI "WINDOWTITLE eq kubectl*" >nul 2>&1
taskkill /F /IM kubectl.exe >nul 2>&1
echo Done.
echo.

echo [2/2] Stopping Minikube...
minikube stop
if %errorlevel% neq 0 (
    echo WARNING: Minikube stop returned an error. It may already be stopped.
)
echo.

echo Backend stopped. Safe to shut down your machine.
pause >nul
