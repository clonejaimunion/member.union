@echo off
setlocal EnableExtensions
cd /d %~dp0
set "APP_DIR=%~dp0"
set "LOG_DIR=%LOCALAPPDATA%\BankDepositSystem\logs"
set "VENV_PY=%APP_DIR%backend\.venv\Scripts\python.exe"
set "WHEEL_DIR=%APP_DIR%backend\wheels"
set "NETWORK_URLS_FILE=%APP_DIR%network_urls.txt"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul

attrib +R "%APP_DIR%backend\server.py" >nul 2>nul
attrib +R "%APP_DIR%frontend\build\*" /S /D >nul 2>nul
icacls "%APP_DIR%backend\server.py" /inheritance:r /grant:r "%USERNAME%:R" Administrators:F SYSTEM:F >nul 2>nul
icacls "%APP_DIR%frontend\build" /inheritance:r /grant:r "%USERNAME%:RX" Administrators:F SYSTEM:F /T >nul 2>nul
cipher /e /s:"%APP_DIR%" >nul 2>nul

set "LAN_IP="
if exist "%NETWORK_URLS_FILE%" del "%NETWORK_URLS_FILE%" >nul 2>nul
for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$items = Get-NetIPConfiguration | Where-Object { $_.IPv4Address -and $_.NetAdapter.Status -eq 'Up' -and $_.IPv4DefaultGateway -and $_.InterfaceAlias -notmatch 'vEthernet|Virtual|VMware|VirtualBox|Loopback|WSL|Docker|Bluetooth|Tailscale|ZeroTier|Npcap' } | ForEach-Object { $_.IPv4Address.IPAddress } | Where-Object { $_ -notmatch '^127\.' -and $_ -notmatch '^169\.254\.' }; if (-not $items) { $items = Get-NetIPConfiguration | Where-Object { $_.IPv4Address -and $_.NetAdapter.Status -eq 'Up' -and $_.InterfaceAlias -notmatch 'vEthernet|Virtual|VMware|VirtualBox|Loopback|WSL|Docker|Bluetooth|Npcap' } | ForEach-Object { $_.IPv4Address.IPAddress } | Where-Object { $_ -notmatch '^127\.' -and $_ -notmatch '^169\.254\.' } }; $items | Select-Object -Unique"`) do (
  if not defined LAN_IP set "LAN_IP=%%I"
  echo http://%%I:8001>>"%NETWORK_URLS_FILE%"
)
if "%LAN_IP%"=="" set "LAN_IP=YOUR-COMPUTER-IP"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Please install Python 3.11.9 once.>"%LOG_DIR%\startup_error.txt"
  exit /b 1
)

set "PY_CMD=python"
where py >nul 2>nul
if not errorlevel 1 (
  py -3.11 --version >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3.11"
)

if not exist "%APP_DIR%backend\.venv" (
  %PY_CMD% -m venv "%APP_DIR%backend\.venv" >>"%LOG_DIR%\startup.log" 2>&1
)

if exist "%WHEEL_DIR%" (
  "%VENV_PY%" -m pip install --no-index --find-links "%WHEEL_DIR%" -r "%APP_DIR%backend\requirements.txt" >>"%LOG_DIR%\startup.log" 2>&1
) else (
  "%VENV_PY%" -m pip install -r "%APP_DIR%backend\requirements.txt" >>"%LOG_DIR%\startup.log" 2>&1
)
if errorlevel 1 (
  echo Requirements installation failed. Check startup.log.>"%LOG_DIR%\startup_error.txt"
  exit /b 1
)

"%VENV_PY%" -m pip show uvicorn >nul 2>nul
if errorlevel 1 (
  echo Uvicorn is not installed correctly.>"%LOG_DIR%\startup_error.txt"
  exit /b 1
)

netsh advfirewall firewall add rule name="Bank Deposit System 8001" dir=in action=allow protocol=TCP localport=8001 >nul 2>nul
wscript.exe "%APP_DIR%run_backend_hidden.vbs"
exit /b 0