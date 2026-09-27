# Installs two shortcuts, both running launcher.py with pythonw.exe (no console window):
#   - shell:startup  "Activity Tracker.lnk"  -> starts monitoring + the tray icon at every logon
#   - Start menu     "Activity Tracker.lnk"  -> searchable in Windows search; runs with --open, so it
#                                               starts the app if you quit it, and opens the window
#   Install:    .\install_startup.ps1
#   Uninstall:  .\install_startup.ps1 -Uninstall

param([switch]$Uninstall)

$launcher = Join-Path $PSScriptRoot "launcher.py"
$icon = Join-Path $PSScriptRoot "icon.ico"
$startupLnk = Join-Path ([Environment]::GetFolderPath("Startup")) "Activity Tracker.lnk"
$startMenuLnk = Join-Path ([Environment]::GetFolderPath("Programs")) "Activity Tracker.lnk"

if ($Uninstall) {
    foreach ($p in @($startupLnk, $startMenuLnk)) {
        if (Test-Path $p) { Remove-Item $p; Write-Host "Removed: $p" }
    }
    Write-Host "If it's running now, right-click the tray icon > Quit."
    exit 0
}

$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) { Write-Error "pythonw.exe isn't on PATH. Install Python from python.org (it ships pythonw.exe)."; exit 1 }

# the shortcuts run whichever pythonw is first on PATH -- make sure that one has the tray deps,
# otherwise it would fail at every login (with a popup, but still)
$python = Join-Path (Split-Path $pythonw) "python.exe"
& $python -c "import pystray, PIL" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "$python is missing the tray dependencies. Run:  `"$python`" -m pip install -r `"$(Join-Path $PSScriptRoot 'requirements.txt')`""
    exit 1
}

& $python $launcher --write-icon $icon  # same drawing as the tray icon

$shell = New-Object -ComObject WScript.Shell
foreach ($spec in @(
    @{ Path = $startupLnk;   Args = "`"$launcher`"";        Desc = "Activity Tracker: start monitoring + tray icon at login" },
    @{ Path = $startMenuLnk; Args = "`"$launcher`" --open"; Desc = "Activity Tracker: goals + monitoring data" }
)) {
    $lnk = $shell.CreateShortcut($spec.Path)
    $lnk.TargetPath = $pythonw
    $lnk.Arguments = $spec.Args
    $lnk.WorkingDirectory = $PSScriptRoot
    $lnk.IconLocation = "$icon,0"
    $lnk.Description = $spec.Desc
    $lnk.Save()
    Write-Host "Installed: $($spec.Path)"
}

Write-Host "Monitoring starts at every login. To open it now, search 'Activity Tracker' in the Start menu."
