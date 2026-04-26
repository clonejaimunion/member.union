@echo off
setlocal
title Bank Deposit Interest System

cd /d %~dp0
set APP_DIR=%~dp0
set VENV_PY=%APP_DIR%backend\.venv\Scripts\python.exe

echo ============================================
echo   Bank Deposit Interest System
echo   Created by Youssef Abdelghany Ahmed
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Please install Python 3.11.9.
  pause
  exit /b 1
)

set PY_CMD=python
where py >nul 2>nul
if not errorlevel 1 (
  py -3.11 --version >nul 2>nul
  if not errorlevel 1 set PY_CMD=py -3.11
)

echo Using Python:
%PY_CMD% --version

if not exist "%APP_DIR%backend\.venv" (
  echo Preparing Python environment...
  %PY_CMD% -m venv "%APP_DIR%backend\.venv"
)

echo Installing/Checking backend requirements...
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r "%APP_DIR%backend\requirements.txt"
if errorlevel 1 (
  echo.
  echo Requirements installation failed.
  echo Please install Python 3.11.9 and make sure internet connection is available.
  pause
  exit /b 1
)

echo Checking application server package...
"%VENV_PY%" -m pip show uvicorn >nul 2>nul
if errorlevel 1 (
  echo Uvicorn was not installed correctly. Installing it now...
  "%VENV_PY%" -m pip install uvicorn
)

echo Starting local system on http://localhost:8001 ...
start "Bank Deposit System" "%APP_DIR%run_backend_server.bat"

timeout /t 4 > nul
start http://localhost:8001

echo.
echo Admin URL: http://localhost:8001/secure-admin-control-panel
echo Username: admin
echo Password: Admin@123
echo.
echo If the app does not start, make sure MongoDB Community Server is installed and running.
pause
