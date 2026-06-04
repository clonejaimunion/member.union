; ============================================================
; محدّث النظام المحاسبي - فبراير 2026 (نسخة مضغوطة LZMA)
; ============================================================

Unicode true
SetCompressor /SOLID lzma
SetCompressorDictSize 32
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
  StrCpy $0 "$LOCALAPPDATA\Bank Deposit Interest System"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done
  StrCpy $0 "$APPDATA\Bank Deposit Interest System"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done
  StrCpy $0 "$PROGRAMFILES64\Bank Deposit Interest System"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done
  StrCpy $0 "$PROGRAMFILES32\Bank Deposit Interest System"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done
  StrCpy $0 "$PROGRAMFILES64\BankDepositSystem"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done
  StrCpy $0 "$PROGRAMFILES32\BankDepositSystem"
  IfFileExists "$0\backend\server.py" 0 +3
    StrCpy $FoundPath "$0"
    Goto done
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
  IfFileExists "$INSTDIR\backend\server.py" continue_install 0
    MessageBox MB_OK|MB_ICONSTOP "لم يتم العثور على ملف server.py داخل:$\r$\n$INSTDIR\backend"
    Abort
  continue_install:

  DetailPrint "إيقاف خدمات البرنامج..."
  nsExec::Exec 'taskkill /F /IM python.exe'
  nsExec::Exec 'taskkill /F /IM pythonw.exe'
  nsExec::Exec 'taskkill /F /IM mongod.exe'
  nsExec::Exec 'taskkill /F /IM wscript.exe'
  Sleep 1500

  ; نسخة احتياطية
  DetailPrint "نسخة احتياطية..."
  RMDir /r "$INSTDIR\backup_feb2026"
  CreateDirectory "$INSTDIR\backup_feb2026"
  CreateDirectory "$INSTDIR\backup_feb2026\backend"
  CopyFiles /SILENT "$INSTDIR\backend\server.py" "$INSTDIR\backup_feb2026\backend\server.py"
  IfFileExists "$INSTDIR\frontend\build\index.html" 0 skip_fe_backup
    CreateDirectory "$INSTDIR\backup_feb2026\frontend_build"
    CopyFiles /SILENT "$INSTDIR\frontend\build\*" "$INSTDIR\backup_feb2026\frontend_build\"
  skip_fe_backup:

  ; Backend (server.py + notifications module only — no external schedulers)
  DetailPrint "تحديث ملفات Backend..."
  SetOutPath "$INSTDIR\backend"
  File "patch\backend\server.py"
  File "patch\backend\deposit_notifications.py"
  File "patch\backend\requirements-runtime.txt"

  ; Remove any legacy PowerShell/VBS/Scheduler artefacts from older versions.
  Delete "$INSTDIR\run_notifier_hidden.vbs"
  Delete "$INSTDIR\register_notifier_task.bat"
  Delete "$INSTDIR\show_toast.ps1"
  Delete "$INSTDIR\backend\notifier_windows.py"
  nsExec::Exec 'schtasks /Delete /TN "BankDepositMaturityNotifier" /F'
  nsExec::Exec 'schtasks /Delete /TN "BankDepositMaturityNotifierHourly" /F'

  ; The optional Python wheels (APScheduler/winsdk/windows-toasts) were
  ; removed from the updater to reduce size — they are not required for
  ; the in-app bell.
  DetailPrint "تخطي wheels الاختيارية (غير مطلوبة)..."

  ; Frontend
  DetailPrint "تحديث الواجهة..."
  RMDir /r "$INSTDIR\frontend\build"
  SetOutPath "$INSTDIR\frontend\build"
  File /r "patch\frontend\*.*"

  DetailPrint "اكتمل التحديث."
SectionEnd

Section -post
  MessageBox MB_OK|MB_ICONINFORMATION "تم تطبيق التحديث بنجاح.$\r$\n$\r$\nالميزات:$\r$\n- نظام تنبيهات استحقاق الودائع داخل البرنامج$\r$\n- معالجة تواريخ ISO من قاعدة البيانات$\r$\n- بدون أي تدخل خارجي (لا PowerShell ولا VBS ولا Scheduler)$\r$\n$\r$\nنسخة احتياطية محفوظة في:$\r$\n$INSTDIR\backup_feb2026"
SectionEnd
