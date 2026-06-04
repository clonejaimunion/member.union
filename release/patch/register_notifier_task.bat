@echo off
REM ============================================================
REM   تسجيل خدمة تنبيهات استحقاق الودائع في جدولة مهام Windows
REM   تعمل عند تسجيل الدخول + كل ساعة (حتى لو البرنامج مغلق)
REM ============================================================

setlocal
chcp 65001 >nul

set "INSTALL_DIR=%~dp0"
set "VBS_PATH=%INSTALL_DIR%run_notifier_hidden.vbs"
set "TASK_NAME=BankDepositMaturityNotifier"
set "TASK_HOURLY=BankDepositMaturityNotifierHourly"

if not exist "%VBS_PATH%" (
    echo [خطأ] لم يتم العثور على %VBS_PATH%
    exit /b 1
)

REM حذف أي تسجيلات قديمة
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1
schtasks /Delete /TN "%TASK_HOURLY%" /F >nul 2>&1

REM مهمة 1: تعمل عند تسجيل الدخول
schtasks /Create /TN "%TASK_NAME%" /TR "wscript.exe \"%VBS_PATH%\"" /SC ONLOGON /RL LIMITED /F >nul

REM مهمة 2: تعمل كل ساعة، 24/7 (حتى لو البرنامج مغلق)
schtasks /Create /TN "%TASK_HOURLY%" /TR "wscript.exe \"%VBS_PATH%\"" /SC HOURLY /MO 1 /RL LIMITED /F >nul

REM تشغيل التنبيهات الآن لأول مرة
start "" wscript.exe "%VBS_PATH%"

echo [✓] تم تسجيل خدمة التنبيهات (عند تسجيل الدخول + كل ساعة)
exit /b 0
