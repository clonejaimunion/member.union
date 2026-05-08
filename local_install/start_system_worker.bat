@echo off
setlocal EnableExtensions
cd /d %~dp0
set "APP_DIR=%~dp0"
set "STATE_DIR=%LOCALAPPDATA%\BankDepositSystem"
set "LOG_DIR=%LOCALAPPDATA%\BankDepositSystem\logs"
set "VENV_PY=%APP_DIR%backend\.venv\Scripts\python.exe"
set "WHEEL_DIR=%APP_DIR%backend\wheels_win"
set "RUNTIME_REQ=%APP_DIR%backend\requirements-runtime.txt"
set "FULL_REQ=%APP_DIR%backend\requirements.txt"
set "DEPS_MARKER=%APP_DIR%backend\.venv\bank_deposit_runtime_ready_py311.flag"
set "HARDEN_MARKER=%STATE_DIR%\installed_files_hardened.flag"
set "MONGO_EXE=%APP_DIR%mongodb\bin\mongod.exe"
set "MONGO_DATA=%STATE_DIR%\mongo-data"
set "MONGO_LOG=%LOG_DIR%\mongodb.log"
set "NETWORK_URLS_FILE=%APP_DIR%network_urls.txt"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul
if exist "%LOG_DIR%\startup_error.txt" del "%LOG_DIR%\startup_error.txt" >nul 2>nul

echo ==== Bank Deposit System startup %DATE% %TIME% ====>>"%LOG_DIR%\startup.log"

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8001/api/health' -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 (
  echo Backend already running.>>"%LOG_DIR%\startup.log"
  exit /b 0
)

if not exist "%HARDEN_MARKER%" (
  attrib +R "%APP_DIR%backend\server.py" >nul 2>nul
  attrib +R "%APP_DIR%frontend\build\*" /S /D >nul 2>nul
  icacls "%APP_DIR%backend\server.py" /inheritance:r /grant:r "%USERNAME%:R" Administrators:F SYSTEM:F >nul 2>nul
  icacls "%APP_DIR%frontend\build" /inheritance:r /grant:r "%USERNAME%:RX" Administrators:F SYSTEM:F /T >nul 2>nul
  cipher /e /s:"%APP_DIR%" >nul 2>nul
  echo done>"%HARDEN_MARKER%"
)

set "LAN_IP="
if exist "%NETWORK_URLS_FILE%" del "%NETWORK_URLS_FILE%" >nul 2>nul
for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$items = Get-NetIPConfiguration | Where-Object { $_.IPv4Address -and $_.NetAdapter.Status -eq 'Up' -and $_.IPv4DefaultGateway -and $_.InterfaceAlias -notmatch 'vEthernet|Virtual|VMware|VirtualBox|Loopback|WSL|Docker|Bluetooth|Tailscale|ZeroTier|Npcap' } | ForEach-Object { $_.IPv4Address.IPAddress } | Where-Object { $_ -notmatch '^127\.' -and $_ -notmatch '^169\.254\.' }; if (-not $items) { $items = Get-NetIPConfiguration | Where-Object { $_.IPv4Address -and $_.NetAdapter.Status -eq 'Up' -and $_.InterfaceAlias -notmatch 'vEthernet|Virtual|VMware|VirtualBox|Loopback|WSL|Docker|Bluetooth|Npcap' } | ForEach-Object { $_.IPv4Address.IPAddress } | Where-Object { $_ -notmatch '^127\.' -and $_ -notmatch '^169\.254\.' } }; $items | Select-Object -Unique"`) do (
  if not defined LAN_IP set "LAN_IP=%%I"
  echo http://%%I:8001>>"%NETWORK_URLS_FILE%"
)
if "%LAN_IP%"=="" set "LAN_IP=YOUR-COMPUTER-IP"

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.11 --version >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3.11"
)
if not defined PY_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
  echo Python 3.11 is not installed. Please install Python 3.11.9 once.>"%LOG_DIR%\startup_error.txt"
  exit /b 1
)

%PY_CMD% -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >>"%LOG_DIR%\startup.log" 2>&1
if errorlevel 1 (
  echo Python 3.11 is required for the bundled offline runtime wheels.>"%LOG_DIR%\startup_error.txt"
  exit /b 1
)

if exist "%APP_DIR%backend\.venv" if not exist "%VENV_PY%" rmdir /S /Q "%APP_DIR%backend\.venv" >>"%LOG_DIR%\startup.log" 2>&1
if not exist "%APP_DIR%backend\.venv" (
  %PY_CMD% -m venv "%APP_DIR%backend\.venv" >>"%LOG_DIR%\startup.log" 2>&1
)
if not exist "%VENV_PY%" (
  echo Virtual environment creation failed. Check startup.log.>"%LOG_DIR%\startup_error.txt"
  exit /b 1
)

set "DEPS_READY=0"
if exist "%DEPS_MARKER%" (
  pushd "%APP_DIR%backend"
  "%VENV_PY%" -c "import fastapi, motor.motor_asyncio, uvicorn, bcrypt, jwt, pyotp, qrcode, arabic_reshaper, bidi, PIL, pypdf, cryptography, reportlab, multipart, server" >nul 2>>"%LOG_DIR%\startup.log"
  if not errorlevel 1 set "DEPS_READY=1"
  popd
)

set "PIP_NO_INPUT=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_DEFAULT_TIMEOUT=15"
set "PIP_RETRIES=1"

if "%DEPS_READY%"=="0" (
  if exist "%WHEEL_DIR%\WINDOWS_WHEELS_READY.txt" (
    echo Installing runtime dependencies from bundled Windows wheels.>>"%LOG_DIR%\startup.log"
    "%VENV_PY%" -m pip install --no-index --find-links "%WHEEL_DIR%" -r "%RUNTIME_REQ%" >>"%LOG_DIR%\startup.log" 2>&1
  ) else (
    echo Bundled Windows wheels are missing; trying online installation with short timeout.>>"%LOG_DIR%\startup.log"
    "%VENV_PY%" -m pip install --timeout 15 --retries 1 -r "%FULL_REQ%" >>"%LOG_DIR%\startup.log" 2>&1
  )
  if errorlevel 1 (
    echo Requirements installation failed. Check startup.log.>"%LOG_DIR%\startup_error.txt"
    exit /b 1
  )
)

pushd "%APP_DIR%backend"
"%VENV_PY%" -c "import fastapi, motor.motor_asyncio, uvicorn, bcrypt, jwt, pyotp, qrcode, arabic_reshaper, bidi, PIL, pypdf, cryptography, reportlab, multipart, server" >>"%LOG_DIR%\startup.log" 2>&1
if errorlevel 1 (
  popd
  echo Runtime dependency verification failed. Check startup.log.>"%LOG_DIR%\startup_error.txt"
  exit /b 1
)
popd
echo ready>"%DEPS_MARKER%"

"%VENV_PY%" -m pip show uvicorn >nul 2>nul
if errorlevel 1 (
  echo Uvicorn is not installed correctly.>"%LOG_DIR%\startup_error.txt"
  exit /b 1
)

if not exist "%MONGO_DATA%" mkdir "%MONGO_DATA%" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $c = New-Object Net.Sockets.TcpClient; $iar = $c.BeginConnect('127.0.0.1',27017,$null,$null); if ($iar.AsyncWaitHandle.WaitOne(1500,$false)) { $c.EndConnect($iar); $c.Close(); exit 0 } else { $c.Close(); exit 1 } } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 goto mongo_ready

echo MongoDB is not responding on port 27017. Trying Windows service.>>"%LOG_DIR%\startup.log"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$svc = Get-Service -Name MongoDB -ErrorAction SilentlyContinue; if ($svc -and $svc.Status -ne 'Running') { try { Start-Service -Name MongoDB -ErrorAction Stop } catch {} }" >>"%LOG_DIR%\startup.log" 2>&1
for /L %%A in (1,1,8) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $c = New-Object Net.Sockets.TcpClient; $iar = $c.BeginConnect('127.0.0.1',27017,$null,$null); if ($iar.AsyncWaitHandle.WaitOne(1000,$false)) { $c.EndConnect($iar); $c.Close(); exit 0 } else { $c.Close(); exit 1 } } catch { exit 1 }" >nul 2>nul
  if not errorlevel 1 goto mongo_ready
  timeout /t 1 /nobreak >nul
)

if exist "%MONGO_EXE%" (
  echo Starting bundled portable MongoDB.>>"%LOG_DIR%\startup.log"
  set "MONGO_EXE_ENV=%MONGO_EXE%"
  set "MONGO_DATA_ENV=%MONGO_DATA%"
  set "MONGO_LOG_ENV=%MONGO_LOG%"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$exe=$env:MONGO_EXE_ENV; $data=$env:MONGO_DATA_ENV; $log=$env:MONGO_LOG_ENV; Start-Process -FilePath $exe -ArgumentList @('--dbpath',$data,'--port','27017','--bind_ip','127.0.0.1','--logpath',$log,'--logappend') -WindowStyle Hidden" >>"%LOG_DIR%\startup.log" 2>&1
) else (
  echo Bundled MongoDB executable is missing.>"%LOG_DIR%\startup_error.txt"
  exit /b 1
)

for /L %%A in (1,1,30) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $c = New-Object Net.Sockets.TcpClient; $iar = $c.BeginConnect('127.0.0.1',27017,$null,$null); if ($iar.AsyncWaitHandle.WaitOne(1000,$false)) { $c.EndConnect($iar); $c.Close(); exit 0 } else { $c.Close(); exit 1 } } catch { exit 1 }" >nul 2>nul
  if not errorlevel 1 goto mongo_ready
  timeout /t 1 /nobreak >nul
)

echo MongoDB did not start. Check mongodb.log.>"%LOG_DIR%\startup_error.txt"
exit /b 1

:mongo_ready
echo MongoDB is ready on 127.0.0.1:27017.>>"%LOG_DIR%\startup.log"

netsh advfirewall firewall add rule name="Bank Deposit System 8001" dir=in action=allow protocol=TCP localport=8001 >nul 2>nul
wscript.exe "%APP_DIR%run_backend_hidden.vbs"
exit /b 0