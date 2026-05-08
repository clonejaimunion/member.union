Option Explicit
Dim shell, fso, appDir, workerPath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
workerPath = appDir & "\run_backend_server.bat"
shell.Run "cmd.exe /c """ & workerPath & """", 0, False