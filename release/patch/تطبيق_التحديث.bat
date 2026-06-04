@echo off
chcp 65001 >nul
title تحديث نظام المحاسبة - فبراير 2026
color 0A

echo.
echo =====================================================
echo    تحديث برنامج النظام المحاسبي (نسخة فبراير 2026)
echo =====================================================
echo.
echo سيتم تطبيق التحديثات التالية:
echo  - التحكم باتجاه طباعة التقارير (طولي / عرضي)
echo  - تحديث تقرير عائد الودائع (المستحقات) لعرض 4 أعمدة
echo  - تحديث كشف العوائد التفريغي بحالة "نشطة حتى تاريخ الاستحقاق"
echo.
pause

REM ----- اكتشاف مجلد تثبيت البرنامج -----
set "TARGET=%~dp0"
if exist "%TARGET%backend\server.py" goto :found
if exist "%ProgramFiles%\BankDepositSystem\backend\server.py" set "TARGET=%ProgramFiles%\BankDepositSystem\"
if exist "%ProgramFiles%\BankDepositSystem\backend\server.py" goto :found
if exist "%ProgramFiles(x86)%\BankDepositSystem\backend\server.py" set "TARGET=%ProgramFiles(x86)%\BankDepositSystem\"
if exist "%ProgramFiles(x86)%\BankDepositSystem\backend\server.py" goto :found

echo [خطأ] لم يتم العثور على مجلد تثبيت البرنامج.
echo ضع هذا الملف داخل مجلد تثبيت BankDepositSystem ثم شغّله مرة أخرى.
pause
exit /b 1

:found
echo.
echo تم العثور على البرنامج في: %TARGET%
echo.

REM ----- إيقاف خدمات البرنامج إذا كانت تعمل -----
echo - إيقاف الخوادم الجارية ...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM mongod.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM ----- نسخ احتياطي للملفات القديمة -----
set "BACKUP=%TARGET%backup_%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%"
set "BACKUP=%BACKUP: =0%"
echo - إنشاء نسخة احتياطية في: %BACKUP%
mkdir "%BACKUP%" 2>nul
mkdir "%BACKUP%\backend" 2>nul
copy /Y "%TARGET%backend\server.py" "%BACKUP%\backend\server.py" >nul
xcopy /E /Y /Q "%TARGET%frontend\build" "%BACKUP%\frontend_build\" >nul

REM ----- تطبيق الملفات الجديدة -----
echo - تحديث ملفات الـ Backend ...
copy /Y "%~dp0backend\server.py" "%TARGET%backend\server.py" >nul

echo - تحديث ملفات الواجهة (Frontend) ...
if exist "%TARGET%frontend\build" rmdir /S /Q "%TARGET%frontend\build"
mkdir "%TARGET%frontend\build" 2>nul
xcopy /E /Y /Q "%~dp0frontend\*" "%TARGET%frontend\build\" >nul

echo.
echo =====================================================
echo  ✓  تم تطبيق التحديث بنجاح
echo =====================================================
echo.
echo نسخة احتياطية محفوظة في:
echo %BACKUP%
echo.
echo شغّل البرنامج من شاشة سطح المكتب لتجربة التحديثات.
echo.
pause
exit /b 0
