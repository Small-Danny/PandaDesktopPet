Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
If CreateObject("Scripting.FileSystemObject").FileExists("dist\PandaDesktopPet\PandaDesktopPet.exe") Then
    WshShell.Run "dist\PandaDesktopPet\PandaDesktopPet.exe", 0, False
Else
    WshShell.Run "pythonw app\main.py", 0, False
End If

