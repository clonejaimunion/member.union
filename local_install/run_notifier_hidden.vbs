' Silent launcher for the deposit maturity notifier (no console window).
Option Explicit
Dim shell, fso, installRoot, pythonExe, notifierPath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

installRoot = fso.GetParentFolderName(WScript.ScriptFullName)

' Prefer the venv pythonw bundled with the app
pythonExe = installRoot & "\backend\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(pythonExe) Then
    pythonExe = installRoot & "\python\pythonw.exe"
End If
If Not fso.FileExists(pythonExe) Then
    pythonExe = "pythonw.exe"
End If

notifierPath = installRoot & "\backend\notifier_windows.py"
If Not fso.FileExists(notifierPath) Then
    WScript.Quit 0
End If

' Run once (Task Scheduler triggers us hourly). 0 = hide, False = don't wait.
shell.Run """" & pythonExe & """ """ & notifierPath & """ --once", 0, False
