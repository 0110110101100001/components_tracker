' Run at login from the HKCU Run key (`pixi run autostart`): `pixi run start`
' with the console window hidden. The argument is the full path to pixi.exe,
' so login does not depend on pixi being on the registry PATH (installing
' pixi without touching PATH is an option).
Option Explicit

Dim shell, files, manifest
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
manifest = files.BuildPath(files.GetParentFolderName(WScript.ScriptFullName), "pixi.toml")
shell.Run Chr(34) & WScript.Arguments(0) & Chr(34) & " run --manifest-path " _
    & Chr(34) & manifest & Chr(34) & " start", 0, False
