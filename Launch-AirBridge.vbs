' AirBridge Silent Launcher
' Created by Chathunga
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)

WshShell.CurrentDirectory = strPath
WshShell.Run "pythonw """ & strPath & "\main.py""", 0, False
