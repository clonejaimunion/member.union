; ========================================================
; محدّث النظام المحاسبي - فبراير 2026
; ========================================================

Unicode true
Name "تحديث النظام المحاسبي - فبراير 2026"
OutFile "BankDepositSystem_Update_Feb2026.exe"
InstallDir "$PROGRAMFILES64\BankDepositSystem"
RequestExecutionLevel admin
ShowInstDetails show

!include "MUI2.nsh"
!define MUI_ICON   "..\local_install\accounting_app.ico"
!define MUI_UNICON "..\local_install\accounting_app.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "Arabic"
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ReadRegStr $0 HKLM "Software\BankDepositSystem" "InstallDir"
  ${If} $0 != ""
    StrCpy $INSTDIR "$0"
  ${EndIf}
  IfFileExists "$PROGRAMFILES64\BankDepositSystem\backend\server.py" 0 +2
    StrCpy $INSTDIR "$PROGRAMFILES64\BankDepositSystem"
  IfFileExists "$PROGRAMFILES32\BankDepositSystem\backend\server.py" 0 +2
    StrCpy $INSTDIR "$PROGRAMFILES32\BankDepositSystem"
FunctionEnd

Section "تطبيق التحديث" SecMain

  DetailPrint "إيقاف الخدمات الجارية..."
  nsExec::Exec 'taskkill /F /IM python.exe'
  nsExec::Exec 'taskkill /F /IM mongod.exe'
  Sleep 1500

  ; التحقق من وجود البرنامج
  IfFileExists "$INSTDIR\backend\server.py" continue_install 0
    MessageBox MB_OK|MB_ICONSTOP "لم يتم العثور على البرنامج في:$\r$\n$INSTDIR$\r$\n$\r$\nيرجى تثبيت البرنامج أولاً أو تحديد مساره يدوياً."
    Abort "البرنامج غير موجود"
  continue_install:

  ; نسخة احتياطية
  DetailPrint "إنشاء نسخة احتياطية..."
  CreateDirectory "$INSTDIR\backup_feb2026"
  CreateDirectory "$INSTDIR\backup_feb2026\backend"
  CopyFiles /SILENT "$INSTDIR\backend\server.py" "$INSTDIR\backup_feb2026\backend\server.py"
  CreateDirectory "$INSTDIR\backup_feb2026\frontend_build"
  CopyFiles /SILENT "$INSTDIR\frontend\build\*" "$INSTDIR\backup_feb2026\frontend_build\"

  ; نسخ ملفات Backend الجديدة
  DetailPrint "تحديث ملفات الـ Backend..."
  SetOutPath "$INSTDIR\backend"
  File "patch\backend\server.py"

  ; نسخ ملفات Frontend الجديدة
  DetailPrint "تحديث ملفات الواجهة..."
  RMDir /r "$INSTDIR\frontend\build"
  SetOutPath "$INSTDIR\frontend\build"
  File /r "patch\frontend\*.*"

  DetailPrint "اكتمل التحديث بنجاح!"

SectionEnd

Section -post
  MessageBox MB_OK|MB_ICONINFORMATION "تم تطبيق التحديث بنجاح.$\r$\n$\r$\nالميزات الجديدة:$\r$\n- التحكم في اتجاه طباعة التقارير (طولي / عرضي)$\r$\n- تقرير عائد الودائع بـ 4 أعمدة + إجمالي عام$\r$\n- كشف العوائد التفريغي بحالة (نشطة حتى تاريخ الاستحقاق)$\r$\n$\r$\nنسخة احتياطية محفوظة في:$\r$\n$INSTDIR\backup_feb2026"
SectionEnd
