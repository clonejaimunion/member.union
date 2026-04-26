Unicode True
Name "Bank Deposit Interest System"
OutFile "..\dist\BankDepositSystemSetup.exe"
InstallDir "$PROGRAMFILES64\Bank Deposit Interest System"
RequestExecutionLevel admin

Page directory
Page instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "..\release\BankDepositSystem\*"

  CreateDirectory "$SMPROGRAMS\Bank Deposit Interest System"
  CreateShortCut "$SMPROGRAMS\Bank Deposit Interest System\تشغيل نظام الودائع.lnk" "$INSTDIR\start_bank_deposit_system.bat"
  CreateShortCut "$DESKTOP\تشغيل نظام الودائع.lnk" "$INSTDIR\start_bank_deposit_system.bat"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\تشغيل نظام الودائع.lnk"
  Delete "$SMPROGRAMS\Bank Deposit Interest System\تشغيل نظام الودائع.lnk"
  RMDir "$SMPROGRAMS\Bank Deposit Interest System"
  RMDir /r "$INSTDIR"
SectionEnd
