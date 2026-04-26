@echo off
setlocal
title نظام عوائد الودائع البنكية

cd /d %~dp0

echo ============================================
echo   نظام عوائد الودائع البنكية
echo   تم إنشاء البرنامج بواسطة يوسف عبدالغني احمد
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
  echo Python غير مثبت على الجهاز. برجاء تثبيت Python 3.11 أو أحدث.
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
echo إذا لم يعمل البرنامج تأكد أن MongoDB Community Server يعمل على الجهاز.
pause
