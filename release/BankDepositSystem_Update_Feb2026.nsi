; ============================================================
; محدّث النظام المحاسبي - فبراير 2026 (نسخة محسّنة)
; يبحث تلقائياً في كل أماكن التثبيت المحتملة
; ============================================================

Unicode true
Name "تحديث النظام المحاسبي - فبراير 2026"
OutFile "BankDepositSystem_Update_Feb2026.exe"
RequestExecutionLevel user
ShowInstDetails show

!include "MUI2.nsh"
!include "LogicLib.nsh"
!define MUI_ICON   "..\local_install\accounting_app.ico"
!define MUI_UNICON "..\local_install\accounting_app.ico"

!define MUI_DIRECTORYPAGE_TEXT_TOP "حدد مجلد تثبيت البرنامج (سيتم اكتشافه تلقائياً)"
!define MUI_DIRECTORYPAGE_TEXT_DESTINATION "مجلد البرنامج"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "Arabic"
!insertmacro MUI_LANGUAGE "English"

Var FoundPath

Function .onInit
  StrCpy $FoundPath ""

  ; 1) المسار الافتراضي للمستخدم الحالي (الأكثر شيوعاً)
  StrCpy $0 "$LOCALAPPDATA\Bank Deposit Interest System"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done

  ; 2) المسار البديل بـ AppData\Roaming
  StrCpy $0 "$APPDATA\Bank Deposit Interest System"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done

  ; 3) ProgramFiles 64-bit
  StrCpy $0 "$PROGRAMFILES64\Bank Deposit Interest System"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done

  ; 4) ProgramFiles 32-bit
  StrCpy $0 "$PROGRAMFILES32\Bank Deposit Interest System"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done

  ; 5) ProgramFiles بدون مسافات (لو الاسم متغيّر)
  StrCpy $0 "$PROGRAMFILES64\BankDepositSystem"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done

  StrCpy $0 "$PROGRAMFILES32\BankDepositSystem"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done

  ; 6) قراءة من Registry (لو سجلّه الـ Setup الأصلي)
  ReadRegStr $0 HKCU "Software\BankDepositSystem" "InstallDir"
  ${If} $0 != ""
    IfFileExists "$0\backend\server.py" 0 +3
      StrCpy $FoundPath "$0"
      Goto done
  ${EndIf}

  ; 7) C:\Bank Deposit Interest System  (لو نسخة بورتابل)
  StrCpy $0 "C:\Bank Deposit Interest System"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done

done:
  ${If} $FoundPath != ""
    StrCpy $INSTDIR "$FoundPath"
  ${Else}
    StrCpy $INSTDIR "$LOCALAPPDATA\Bank Deposit Interest System"
  ${EndIf}
FunctionEnd

Function .onVerifyInstDir
  IfFileExists "$INSTDIR\backend\server.py" PathGood 0
    Abort
  PathGood:
FunctionEnd

Section "تطبيق التحديث" SecMain

  ; التحقق النهائي
  IfFileExists "$INSTDIR\backend\server.py" continue_install 0
    MessageBox MB_OK|MB_ICONSTOP "لم يتم العثور على ملف server.py داخل:$\r$\n$INSTDIR\backend$\r$\n$\r$\nاضغط رجوع وحدد المجلد الصحيح يدوياً."
    Abort
  continue_install:

  DetailPrint "إيقاف خدمات البرنامج..."
  nsExec::Exec 'taskkill /F /IM python.exe'
  nsExec::Exec 'taskkill /F /IM pythonw.exe'
  nsExec::Exec 'taskkill /F /IM mongod.exe'
  nsExec::Exec 'taskkill /F /IM wscript.exe'
  Sleep 1500

  ; نسخة احتياطية
  DetailPrint "إنشاء نسخة احتياطية في backup_feb2026..."
  RMDir /r "$INSTDIR\backup_feb2026"
  CreateDirectory "$INSTDIR\backup_feb2026"
  CreateDirectory "$INSTDIR\backup_feb2026\backend"
  CopyFiles /SILENT "$INSTDIR\backend\server.py" "$INSTDIR\backup_feb2026\backend\server.py"
  IfFileExists "$INSTDIR\frontend\build\index.html" 0 skip_fe_backup
    CreateDirectory "$INSTDIR\backup_feb2026\frontend_build"
    CopyFiles /SILENT "$INSTDIR\frontend\build\*" "$INSTDIR\backup_feb2026\frontend_build\"
  skip_fe_backup:

  ; نسخ ملفات Backend الجديدة
  DetailPrint "تحديث server.py..."
  SetOutPath "$INSTDIR\backend"
  File "patch\backend\server.py"

  ; نسخ ملفات Frontend الجديدة
  DetailPrint "تحديث ملفات الواجهة..."
  RMDir /r "$INSTDIR\frontend\build"
  SetOutPath "$INSTDIR\frontend\build"
  File /r "patch\frontend\*.*"

  DetailPrint "اكتمل التحديث بنجاح."

SectionEnd

Section -post
  MessageBox MB_OK|MB_ICONINFORMATION "تم تطبيق التحديث بنجاح.$\r$\n$\r$\nالميزات الجديدة:$\r$\n- التحكم في اتجاه طباعة التقارير (طولي / عرضي)$\r$\n- تقرير عائد الودائع بـ 4 أعمدة + إجمالي عام$\r$\n- كشف العوائد التفريغي بحالة (نشطة حتى تاريخ الاستحقاق)$\r$\n$\r$\nنسخة احتياطية محفوظة في:$\r$\n$INSTDIR\backup_feb2026"
SectionEnd
