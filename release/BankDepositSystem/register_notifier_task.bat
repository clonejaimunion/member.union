@echo off
REM ============================================================
REM   تسجيل خدمة تنبيهات استحقاق الودائع في جدولة مهام Windows
REM ============================================================
REM يتم استدعاؤه تلقائياً بعد التثبيت من NSIS.
REM يقوم بتسجيل مهمة باسم BankDepositMaturityNotifier تعمل عند
REM تسجيل الدخول لكل مستخدم على هذا الجهاز.

setlocal
chcp 65001 >nul

set "INSTALL_DIR=%~dp0"
set "VBS_PATH=%INSTALL_DIR%run_notifier_hidden.vbs"
set "TASK_NAME=BankDepositMaturityNotifier"

if not exist "%VBS_PATH%" (
    echo [خطأ] لم يتم العثور على %VBS_PATH%
    exit /b 1
)

REM حذف أي تسجيل قديم للمهمة (تجاهل الأخطاء)
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

REM تسجيل مهمة جديدة تعمل عند تسجيل دخول المستخدم وتشغل في الخلفية
schtasks /Create ^
    /TN "%TASK_NAME%" ^
    /TR "wscript.exe \"%VBS_PATH%\"" ^
    /SC ONLOGON ^
    /RL LIMITED ^
    /F >nul

if errorlevel 1 (
    echo [تحذير] فشل تسجيل المهمة. شغل الأمر يدوياً كمسؤول.
    exit /b 1
)

REM تشغيل التنبيهات الآن لأول مرة بدون انتظار إعادة تسجيل الدخول
start "" wscript.exe "%VBS_PATH%"

echo [✓] تم تسجيل خدمة التنبيهات بنجاح.
exit /b 0
