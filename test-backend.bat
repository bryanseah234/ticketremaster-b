@echo off
title TicketRemaster - Run Gateway Tests
echo ============================================
echo  TicketRemaster - Gateway Tests
echo ============================================
echo.

cd /d "%~dp0"

echo Running tests against PUBLIC URL (ticketremasterapi.hong-yi.me)...
echo.
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-public.postman_environment.json --reporters cli

echo.
echo ============================================
echo Running tests against LOCALHOST (port-forward must be running)...
echo ============================================
echo.
newman run postman/TicketRemaster.gateway.postman_collection.json -e postman/TicketRemaster.gateway-localhost.postman_environment.json --reporters cli

echo.
echo Done! Press any key to close.
pause >nul
