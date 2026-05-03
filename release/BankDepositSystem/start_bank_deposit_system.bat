@echo off
setlocal
title Bank Deposit Interest System

cd /d %~dp0
set APP_DIR=%~dp0
set VENV_PY=%APP_DIR%backend\.venv\Scripts\python.exe
set WHEEL_DIR=%APP_DIR%backend\wheels

attrib +R "%APP_DIR%backend\server.py" >nul 2>nul
attrib +R "%APP_DIR%frontend\build\*" /S /D >nul 2>nul
icacls "%APP_DIR%backend\server.py" /inheritance:r /grant:r "%USERNAME%:R" Administrators:F SYSTEM:F >nul 2>nul
icacls "%APP_DIR%frontend\build" /inheritance:r /grant:r "%USERNAME%:RX" Administrators:F SYSTEM:F /T >nul 2>nul
cipher /e /s:"%APP_DIR%" >nul 2>nul

echo ============================================
echo   Bank Deposit Interest System
echo   Created by Youssef Abdelghany Ahmed
echo ============================================
echo.
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } | Select-Object -First 1 -ExpandProperty IPAddress)"`) do set LAN_IP=%%I
if "%LAN_IP%"=="" set LAN_IP=YOUR-COMPUTER-IP

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Please install Python 3.11.9 once, then run the system again.
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

echo Installing/Checking backend requirements locally...
if exist "%WHEEL_DIR%" (
  "%VENV_PY%" -m pip install --no-index --find-links "%WHEEL_DIR%" -r "%APP_DIR%backend\requirements.txt"
) else (
  echo Local dependency folder was not found. Trying normal installation...
  "%VENV_PY%" -m pip install -r "%APP_DIR%backend\requirements.txt"
)
if errorlevel 1 (
  echo.
  echo Requirements installation failed.
  echo Make sure the installer includes backend\wheels, or connect once to install requirements.
  pause
  exit /b 1
)

echo Checking application server package...
"%VENV_PY%" -m pip show uvicorn >nul 2>nul
if errorlevel 1 (
  echo Uvicorn was not installed correctly from local packages.
  pause
  exit /b 1
)

echo Starting local system on http://localhost:8001 ...
echo Network access on other computers: http://%LAN_IP%:8001
netsh advfirewall firewall add rule name="Bank Deposit System 8001" dir=in action=allow protocol=TCP localport=8001 >nul 2>nul
start "Bank Deposit System" "%APP_DIR%run_backend_server.bat"

timeout /t 4 > nul
start http://localhost:8001

echo.
echo Admin URL: http://localhost:8001/secure-admin-control-panel
echo Network URL: http://%LAN_IP%:8001
echo Use the Network URL from any computer connected to the same local network.
echo Username: admin
echo Password: Admin@123
echo.
echo If the app does not start, make sure MongoDB Community Server is installed and running.
pause
