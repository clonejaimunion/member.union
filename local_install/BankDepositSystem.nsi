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

  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\Bank Deposit System.lnk"
  Delete "$SMPROGRAMS\Bank Deposit Interest System\Bank Deposit System.lnk"
  RMDir "$SMPROGRAMS\Bank Deposit Interest System"
  RMDir /r "$INSTDIR"
SectionEnd
