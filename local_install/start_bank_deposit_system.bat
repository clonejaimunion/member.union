@echo off
setlocal EnableExtensions
cd /d %~dp0
wscript.exe "%~dp0launch_bank_deposit_system.vbs"
exit /b 0