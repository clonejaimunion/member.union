@echo off
setlocal
title Bank Deposit Interest System

cd /d %~dp0

echo ============================================
echo   Bank Deposit Interest System
echo   Created by Youssef Abdelghany Ahmed
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Please install Python 3.11 or newer.
  pause
  exit /b 1
)

if not exist backend\.venv (
  echo Preparing Python environment...
  python -m venv backend\.venv
)

call backend\.venv\Scripts\activate
echo Installing/Checking backend requirements...
pip install -r backend\requirements.txt

echo Starting local system on http://localhost:8001 ...
start "Bank Deposit System" cmd /k "cd /d %cd%\backend && call .venv\Scripts\activate && uvicorn server:app --host 127.0.0.1 --port 8001"

timeout /t 4 > nul
start http://localhost:8001

echo.
echo Admin URL: http://localhost:8001/secure-admin-control-panel
echo Username: admin
echo Password: Admin@123
echo.
echo If the app does not start, make sure MongoDB Community Server is installed and running.
pause
