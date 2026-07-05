# Creates a shell:startup shortcut that runs launcher.py with pythonw.exe
# (no console window) at every logon. Run once:  .\install_startup.ps1
# Remove by deleting "Accountability.lnk" from shell:startup.

$launcher = Join-Path $PSScriptRoot "launcher.py"
$pythonw = (Get-Command pythonw.exe).Source
$startup = [Environment]::GetFolderPath("Startup")
$lnkPath = Join-Path $startup "Accountability.lnk"

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath = $pythonw
$lnk.Arguments = "`"$launcher`""
$lnk.WorkingDirectory = $PSScriptRoot
$lnk.Description = "Accountability tracker + tray"
$lnk.Save()

Write-Host "Installed: $lnkPath"
Write-Host "It will start at next logon. To start it now:  pythonw `"$launcher`""
