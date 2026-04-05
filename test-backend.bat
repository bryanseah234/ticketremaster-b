@echo off
title TicketRemaster - Run Gateway Tests
echo ============================================
echo  TicketRemaster - Gateway Tests
echo ============================================
echo.
echo Which tests do you want to run?
echo   1. Public URL only (ticketremasterapi.hong-yi.me) - no port-forward needed
echo   2. Localhost only  (localhost:8000) - requires port-forward running
echo   3. Both
echo.
set /p choice="Enter 1, 2 or 3: "

cd /d "%~dp0"

if "%choice%"=="1" goto public
if "%choice%"=="2" goto local
if "%choice%"=="3" goto both
echo Invalid choice. Running public URL tests by default.
goto public

:public
echo.
echo Running tests against PUBLIC URL...
echo.
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli
goto end

:local
echo.
echo Running tests against LOCALHOST (make sure port-forward is running)...
echo.
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli
goto end

:both
echo.
echo Running tests against PUBLIC URL...
echo.
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli
echo.
echo Running tests against LOCALHOST...
echo.
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli

:end
echo.
echo Done! Press any key to close.
pause >nul
