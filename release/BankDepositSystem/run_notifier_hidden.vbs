' Silent launcher for the deposit maturity notifier (no console window).
' Run on Windows logon via Task Scheduler.
Option Explicit
Dim shell, fso, installRoot, pythonExe, notifierPath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Resolve install root: same folder as this VBS file.
installRoot = fso.GetParentFolderName(WScript.ScriptFullName)

' Prefer bundled python if present, otherwise system pythonw.
pythonExe = installRoot & "\python\pythonw.exe"
If Not fso.FileExists(pythonExe) Then
    pythonExe = "pythonw.exe"
End If

notifierPath = installRoot & "\backend\notifier_windows.py"
If Not fso.FileExists(notifierPath) Then
    WScript.Quit 0
End If

' 0 = hide window, False = do not wait.
shell.Run """" & pythonExe & """ """ & notifierPath & """", 0, False
