@echo off
setlocal EnableExtensions
cd /d %~dp0backend
set "LOG_DIR=%LOCALAPPDATA%\BankDepositSystem\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul
"%~dp0backend\.venv\Scripts\python.exe" -m uvicorn server:app --host 0.0.0.0 --port 8001 >>"%LOG_DIR%\server.log" 2>&1
exit /b 0