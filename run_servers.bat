@echo off
title Vyom (Vector-Eye) v2.0 Control Center
color 0B
cls

echo ======================================================================
echo           ⚡ VYOM (VECTOR-EYE) v2.0 - CONTROL CENTER ⚡
echo   Autonomous Google Ads Sector Intelligence & Competitor Engine
echo ======================================================================
echo.

echo [*] Starting Backend API Server (FastAPI on Port 8000)...
start "Vyom Backend API" cmd /k "color 0A && python main_api.py"

echo [*] Starting Frontend Dashboard (Vite on Port 3000)...
start "Vyom Frontend Dashboard" cmd /k "color 0D && cd frontend && npm run dev"

echo.
echo ======================================================================
echo [OK] Both servers have been launched in separate windows!
echo.
echo    - FastAPI Backend:   http://localhost:8000
echo    - React Dashboard:   http://localhost:3000
echo.
echo Keep this window open if you want to keep track or stop both later.
echo ======================================================================
echo.
pause
