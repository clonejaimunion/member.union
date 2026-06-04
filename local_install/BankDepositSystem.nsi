Unicode True
Name "Bank Deposit Interest System"
OutFile "..\dist\BankDepositSystemSetup.exe"
Icon "accounting_app.ico"
UninstallIcon "accounting_app.ico"
InstallDir "$LOCALAPPDATA\Bank Deposit Interest System"
RequestExecutionLevel user

Page directory
Page instfiles

Section "Install"
  RMDir /r "$INSTDIR\frontend\build"
  Delete "$INSTDIR\reset_super_admin_2fa.bat"
  Delete "$INSTDIR\backend\reset_super_admin_2fa.py"
  SetOutPath "$INSTDIR"
  File /r "..\release\BankDepositSystem\*"

  CreateDirectory "$SMPROGRAMS\Bank Deposit Interest System"
  CreateShortCut "$SMPROGRAMS\Bank Deposit Interest System\Bank Deposit System.lnk" "$SYSDIR\wscript.exe" '"$INSTDIR\launch_bank_deposit_system.vbs"' "$INSTDIR\accounting_app.ico" 0
  CreateShortCut "$DESKTOP\Bank Deposit System.lnk" "$SYSDIR\wscript.exe" '"$INSTDIR\launch_bank_deposit_system.vbs"' "$INSTDIR\accounting_app.ico" 0

  ; Register the deposit-maturity notifier as a Windows Task Scheduler entry
  ; that runs at user logon. The .bat handles both registration and immediate start.
  nsExec::ExecToLog '"$INSTDIR\register_notifier_task.bat"'

  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  ; Remove both scheduled notifier tasks on uninstall.
  nsExec::ExecToLog 'schtasks /Delete /TN "BankDepositMaturityNotifier" /F'
  nsExec::ExecToLog 'schtasks /Delete /TN "BankDepositMaturityNotifierHourly" /F'
  Delete "$DESKTOP\Bank Deposit System.lnk"
  Delete "$SMPROGRAMS\Bank Deposit Interest System\Bank Deposit System.lnk"
  RMDir "$SMPROGRAMS\Bank Deposit Interest System"
  RMDir /r "$INSTDIR"
SectionEnd
