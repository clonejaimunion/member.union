@echo off
setlocal
title Reset Super Admin 2FA

cd /d %~dp0
set APP_DIR=%~dp0
set VENV_PY=%APP_DIR%backend\.venv\Scripts\python.exe
set WHEEL_DIR=%APP_DIR%backend\wheels

echo ============================================
echo   Reset Super Admin Google Authenticator
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Please install Python 3.11.9 once, then run this tool again.
  pause
  exit /b 1
)

set PY_CMD=python
where py >nul 2>nul
if not errorlevel 1 (
  py -3.11 --version >nul 2>nul
  if not errorlevel 1 set PY_CMD=py -3.11
)

if not exist "%APP_DIR%backend\.venv" (
  echo Preparing Python environment...
  %PY_CMD% -m venv "%APP_DIR%backend\.venv"
)

"%VENV_PY%" -c "import pymongo, dotenv" >nul 2>nul
if errorlevel 1 (
  echo Installing local requirements...
  if exist "%WHEEL_DIR%" (
    "%VENV_PY%" -m pip install --no-index --find-links "%WHEEL_DIR%" -r "%APP_DIR%backend\requirements.txt"
  ) else (
    "%VENV_PY%" -m pip install -r "%APP_DIR%backend\requirements.txt"
  )
)

echo.
echo This will disable Google Authenticator for the hidden super admin only.
echo It will not delete accounting data.
echo.
set /p CONFIRM=Type YES to continue: 
if /I not "%CONFIRM%"=="YES" (
  echo Cancelled.
  pause
  exit /b 0
)

"%VENV_PY%" "%APP_DIR%backend\reset_super_admin_2fa.py"
echo.
pause