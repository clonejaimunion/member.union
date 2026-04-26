@echo off
setlocal
title Bank Deposit Interest System - Local Run

echo ============================================
echo  Bank Deposit Interest System - Local Setup
echo ============================================

cd /d %~dp0\..

if not exist backend\.venv (
  echo Creating Python virtual environment...
  python -m venv backend\.venv
)

call backend\.venv\Scripts\activate
echo Installing backend dependencies...
pip install -r backend\requirements.txt

echo Installing frontend dependencies...
cd frontend
call yarn install
cd ..

echo Starting backend on http://localhost:8001 ...
start "Bank Backend" cmd /k "cd /d %cd%\backend && call .venv\Scripts\activate && uvicorn server:app --host 0.0.0.0 --port 8001"

echo Starting frontend on http://localhost:3000 ...
start "Bank Frontend" cmd /k "cd /d %cd%\frontend && set REACT_APP_BACKEND_URL=http://localhost:8001 && yarn start"

timeout /t 5 > nul
start http://localhost:3000

echo Done. Admin URL: http://localhost:3000/secure-admin-control-panel
pause
