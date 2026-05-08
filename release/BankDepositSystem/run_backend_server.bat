@echo off
setlocal EnableExtensions
cd /d %~dp0backend
set "LOG_DIR=%LOCALAPPDATA%\BankDepositSystem\logs"
set "VENV_PY=%~dp0backend\.venv\Scripts\python.exe"
set "PYTHONUNBUFFERED=1"
set "PYTHONIOENCODING=utf-8"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul
echo ==== Backend server startup %DATE% %TIME% ====>>"%LOG_DIR%\server.log"
if not exist "%VENV_PY%" (
  echo Virtual environment python is missing.>>"%LOG_DIR%\server.log"
  exit /b 1
)
"%VENV_PY%" -m uvicorn server:app --host 0.0.0.0 --port 8001 >>"%LOG_DIR%\server.log" 2>&1
exit /b 0