Option Explicit
Dim shell, fso, appDir, splashPath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
splashPath = appDir & "\splash.hta"
shell.Run "mshta.exe """ & splashPath & """", 1, False