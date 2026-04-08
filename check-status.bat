@echo off
setlocal EnableExtensions

title TicketRemaster Status Check
echo ============================================
echo  TicketRemaster - Status Check
echo ============================================
echo.

cd /d "%~dp0"

set "EXIT_CODE=0"
set "LOCAL_GATEWAY_STATE_FILE=.local-gateway-url"
set "LOCAL_GATEWAY_URL=http://localhost:8000"

if exist "%LOCAL_GATEWAY_STATE_FILE%" (
    set /p "LOCAL_GATEWAY_URL="<"%LOCAL_GATEWAY_STATE_FILE%"
)

where kubectl >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: kubectl was not found in PATH. Skipping pod checks.
    echo.
    set "EXIT_CODE=1"
) else (
    echo [Pods - Core]
    kubectl get pods -n ticketremaster-core
    if errorlevel 1 (
        echo   [!!] Unable to query namespace ticketremaster-core
        set "EXIT_CODE=1"
    )
    echo.

    echo [Pods - Data]
    kubectl get pods -n ticketremaster-data
    if errorlevel 1 (
        echo   [!!] Unable to query namespace ticketremaster-data
        set "EXIT_CODE=1"
    )
    echo.

    echo [Pods - Edge]
    kubectl get pods -n ticketremaster-edge
    if errorlevel 1 (
        echo   [!!] Unable to query namespace ticketremaster-edge
        set "EXIT_CODE=1"
    )
    echo.
)

echo [Localhost Gateway]
where powershell >nul 2>&1
if %errorlevel% neq 0 (
    echo   [!!] Windows PowerShell was not found in PATH.
    set "EXIT_CODE=1"
) else (
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest '%LOCAL_GATEWAY_URL%/events' -UseBasicParsing -TimeoutSec 5; Write-Host '  [OK] %LOCAL_GATEWAY_URL% -' $r.StatusCode } catch { Write-Host '  [!!] %LOCAL_GATEWAY_URL% unreachable' }"
    if errorlevel 1 set "EXIT_CODE=1"
)

echo.
echo [Public Gateway]
where powershell >nul 2>&1
if %errorlevel% neq 0 (
    echo   [!!] Windows PowerShell was not found in PATH.
    set "EXIT_CODE=1"
) else (
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest 'https://ticketremasterapi.hong-yi.me/events' -UseBasicParsing -TimeoutSec 10; Write-Host '  [OK] ticketremasterapi.hong-yi.me -' $r.StatusCode } catch { Write-Host '  [!!] ticketremasterapi.hong-yi.me unreachable' }"
    if errorlevel 1 set "EXIT_CODE=1"
)

echo.
if "%EXIT_CODE%"=="0" (
    echo Status check completed.
) else (
    echo Status check completed with warnings.
)
pause
exit /b %EXIT_CODE%
