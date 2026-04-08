@echo off
setlocal EnableExtensions

title TicketRemaster - Run Gateway Tests
echo ============================================
echo  TicketRemaster - Gateway Tests
echo ============================================
echo.

cd /d "%~dp0"

set "COLLECTION_FILE=postman\TicketRemaster.gateway.postman_collection.json"
set "PUBLIC_ENV_FILE=postman\TicketRemaster.gateway-public.postman_environment.json"
set "LOCAL_ENV_FILE=postman\TicketRemaster.gateway-localhost.postman_environment.json"
set "LOCAL_GATEWAY_STATE_FILE=.local-gateway-url"
set "LOCAL_GATEWAY_URL=http://localhost:8000"
set "OVERALL_EXIT=0"

if exist "%LOCAL_GATEWAY_STATE_FILE%" (
    set /p "LOCAL_GATEWAY_URL="<"%LOCAL_GATEWAY_STATE_FILE%"
)

where newman >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Newman CLI was not found in PATH.
    echo Install "newman" and try again.
    goto fail
)
if not exist "%COLLECTION_FILE%" (
    echo ERROR: Gateway Postman collection not found.
    echo Expected path: %~dp0%COLLECTION_FILE%
    goto fail
)
if not exist "%PUBLIC_ENV_FILE%" (
    echo ERROR: Public gateway Postman environment not found.
    echo Expected path: %~dp0%PUBLIC_ENV_FILE%
    goto fail
)
if not exist "%LOCAL_ENV_FILE%" (
    echo ERROR: Localhost gateway Postman environment not found.
    echo Expected path: %~dp0%LOCAL_ENV_FILE%
    goto fail
)

echo Which tests do you want to run?
echo   1. Public URL only (ticketremasterapi.hong-yi.me) - no port-forward needed
echo   2. Localhost only  (%LOCAL_GATEWAY_URL%) - requires port-forward running
echo   3. Both
echo.
set /p "choice=Enter 1, 2 or 3 (default: 1): "
if "%choice%"=="" set "choice=1"

if "%choice%"=="1" goto public
if "%choice%"=="2" goto local
if "%choice%"=="3" goto both
echo Invalid choice. Running public URL tests by default.
goto public

:public
echo.
echo Running tests against PUBLIC URL...
echo.
newman run "%COLLECTION_FILE%" -e "%PUBLIC_ENV_FILE%" --reporters cli
if errorlevel 1 (
    echo ERROR: Newman reported a failure for PUBLIC URL.
    set "OVERALL_EXIT=1"
)
goto end

:local
echo.
echo Running tests against LOCALHOST (make sure port-forward is running)...
echo.
newman run "%COLLECTION_FILE%" -e "%LOCAL_ENV_FILE%" --env-var "gateway_url=%LOCAL_GATEWAY_URL%" --reporters cli
if errorlevel 1 (
    echo ERROR: Newman reported a failure for LOCALHOST.
    set "OVERALL_EXIT=1"
)
goto end

:both
echo.
echo Running tests against PUBLIC URL...
echo.
newman run "%COLLECTION_FILE%" -e "%PUBLIC_ENV_FILE%" --reporters cli
if errorlevel 1 (
    echo ERROR: Newman reported a failure for PUBLIC URL.
    set "OVERALL_EXIT=1"
)
echo.
echo Running tests against LOCALHOST...
echo.
newman run "%COLLECTION_FILE%" -e "%LOCAL_ENV_FILE%" --env-var "gateway_url=%LOCAL_GATEWAY_URL%" --reporters cli
if errorlevel 1 (
    echo ERROR: Newman reported a failure for LOCALHOST.
    set "OVERALL_EXIT=1"
)

:end
echo.
if "%OVERALL_EXIT%"=="0" (
    echo Done! Press any key to close.
) else (
    echo One or more test runs failed. Press any key to close.
)
pause >nul
exit /b %OVERALL_EXIT%

:fail
echo.
echo Unable to start backend tests. Press any key to close.
pause >nul
exit /b 1
