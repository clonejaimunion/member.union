@echo off
setlocal
title Bank Deposit System Server

cd /d %~dp0backend
"%~dp0backend\.venv\Scripts\python.exe" -m uvicorn server:app --host 0.0.0.0 --port 8001

echo.
echo Server stopped. Press any key to close.
pause >nul
