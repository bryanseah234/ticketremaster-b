@echo off
title TicketRemaster Status Check
echo ============================================
echo  TicketRemaster - Status Check
echo ============================================
echo.

echo [Pods - Core]
kubectl get pods -n ticketremaster-core
echo.

echo [Pods - Data]
kubectl get pods -n ticketremaster-data
echo.

echo [Pods - Edge]
kubectl get pods -n ticketremaster-edge
echo.

echo [Localhost Gateway]
powershell -NoProfile -Command "try { $r = Invoke-WebRequest http://localhost:8000/events -UseBasicParsing -TimeoutSec 5; Write-Host '  [OK] localhost:8000 -' $r.StatusCode } catch { Write-Host '  [!!] localhost:8000 unreachable' }"

echo.
echo [Public Gateway]
powershell -NoProfile -Command "try { $r = Invoke-WebRequest https://ticketremasterapi.hong-yi.me/events -UseBasicParsing -TimeoutSec 10; Write-Host '  [OK] ticketremasterapi.hong-yi.me -' $r.StatusCode } catch { Write-Host '  [!!] ticketremasterapi.hong-yi.me unreachable' }"

echo.
pause
