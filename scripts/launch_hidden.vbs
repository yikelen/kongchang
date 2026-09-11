Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
exe = dir & "\vendor\python\pythonw.exe"
app = dir & "\src\main.py"
If Not fso.FileExists(exe) Then
  WScript.Quit 1
End If
Set sh = CreateObject("Wscript.Shell")
sh.CurrentDirectory = dir
sh.Run """" & exe & """ """ & app & """", 0, False
