Option Explicit

Dim shell, fileSystem, command, argument
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

shell.CurrentDirectory = fileSystem.GetParentFolderName(WScript.ScriptFullName)
command = """.venv\Scripts\pythonw.exe"" -m home_finder.web_app_v7"

For Each argument In WScript.Arguments
    command = command & " " & QuoteArgument(CStr(argument))
Next

' pythonw has no console window, so the local server stays invisible.
shell.Run command, 0, False

Function QuoteArgument(value)
    QuoteArgument = """" & Replace(value, """", """""") & """"
End Function
