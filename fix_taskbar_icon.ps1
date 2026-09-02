# ============================================================================
# Fix: taskbar shows the blue icon.ico instead of the green icon_modern.ico
#
# WHY: the code fix (window-level setWindowIcon in ModernMainWindow) works —
# the app reports the green icon to Windows via WM_GETICON. But the Windows
# taskbar groups a running app with its Start Menu shortcut and shows the
# SHORTCUT's icon. The installed shortcut pins {app}\icon.ico (blue), so the
# taskbar shows blue. This script repoints the shortcut to icon_modern.ico
# (green) and refreshes the icon cache.
#
# RUN AS ADMINISTRATOR:
#   powershell -ExecutionPolicy Bypass -File .\fix_taskbar_icon.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

# --- require admin ---
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent() `
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Diese Skript muss als Administrator ausgefuehrt werden:" -ForegroundColor Red
    Write-Host '  powershell -ExecutionPolicy Bypass -File .\fix_taskbar_icon.ps1' -ForegroundColor Yellow
    Write-Host '...mit Rechtsklick "Als Administrator ausfuehren".' -ForegroundColor Yellow
    exit 1
}

$installDir = "C:\Program Files\WakeOnLAN"
$srcModern = Join-Path $PSScriptRoot "icon_modern.ico"
if (-not (Test-Path $srcModern)) {
    Write-Host "icon_modern.ico nicht gefunden unter: $srcModern" -ForegroundColor Red
    exit 1
}
$modernTarget = Join-Path $installDir "icon_modern.ico"

# Current UI mode from the user config -> icon for the shortcut.
$mode = "modern"
$cfgPath = Join-Path $env:USERPROFILE ".wol_app\config.json"
if (Test-Path $cfgPath) {
    try { $mode = (Get-Content $cfgPath -Raw | ConvertFrom-Json).ui.layout_mode } catch { }
}
if ($mode -notin @("modern", "classic")) { $mode = "modern" }
Write-Host "UI-Modus laut Konfiguration: $mode" -ForegroundColor Cyan

Write-Host "[1/4] icon_modern.ico in die Installation kopieren..." -ForegroundColor Yellow
Copy-Item $srcModern $modernTarget -Force
Write-Host "  OK: $modernTarget" -ForegroundColor Green

Write-Host "[2/4] Installierte EXE durch aktuellen Build ersetzen..." -ForegroundColor Yellow
$srcExe = Join-Path $PSScriptRoot "dist\Wake-on-LAN Manager.exe"
$dstExe = Join-Path $installDir "Wake-on-LAN Manager.exe"
if (Test-Path $srcExe) {
    Get-Process "Wake-on-LAN Manager" -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Milliseconds 400
    Copy-Item $srcExe $dstExe -Force
    Write-Host "  OK: $($srcExe) -> $dstExe" -ForegroundColor Green
} else {
    Write-Host "  (kein dist-Build gefunden - zuerst .\build.ps1 ausfuehren)" -ForegroundColor Yellow
}

Write-Host "[3/4] Startmenue-/Desktop-Verknuepfung auf das Icon des UI-Modus setzen..." -ForegroundColor Yellow
$iconForMode = if ($mode -eq "modern") { $modernTarget } else { Join-Path $installDir "icon.ico" }
$shell = New-Object -ComObject WScript.Shell
$shortcutPaths = @(
    "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Wake-on-LAN Manager\Wake-on-LAN Manager.lnk",
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Wake-on-LAN Manager\Wake-on-LAN Manager.lnk",
    "$env:USERPROFILE\Desktop\Wake-on-LAN Manager.lnk",
    "$env:PUBLIC\Desktop\Wake-on-LAN Manager.lnk"
)
$fixed = 0
foreach ($p in $shortcutPaths) {
    if (Test-Path $p) {
        $sc = $shell.CreateShortcut($p)
        $sc.IconLocation = "$iconForMode,0"
        $sc.Save()
        Write-Host "  OK: $p" -ForegroundColor Green
        $fixed++
    }
}
if ($fixed -eq 0) { Write-Host "  (keine Verknuepfung gefunden)" -ForegroundColor DarkGray }

Write-Host "[4/4] Windows-Icon-Cache aktualisieren..." -ForegroundColor Yellow
Get-Process "Wake-on-LAN Manager" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 400
$cacheDir = "$env:LOCALAPPDATA\Microsoft\Windows\Explorer"
Get-ChildItem $cacheDir -Filter "iconcache*" -Force -ErrorAction SilentlyContinue | ForEach-Object {
    try { Remove-Item $_.FullName -Force -ErrorAction Stop; Write-Host "  removed $($_.Name)" -ForegroundColor DarkGray }
    catch { Write-Host "  belegt (wird von Windows neu erstellt): $($_.Name)" -ForegroundColor DarkGray }
}
Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 800
if (-not (Get-Process -Name explorer -ErrorAction SilentlyContinue)) { Start-Process explorer }

Write-Host ""
Write-Host "Fertig. Die Taskleiste folgt jetzt dem aktiven UI-Modus:" -ForegroundColor Green
Write-Host "  Moderne UI  -> gruenes Icon" -ForegroundColor Green
Write-Host "  Klassische UI -> blaues Icon" -ForegroundColor Blue
Write-Host "(Nach einem UI-Wechsel in den Einstellungen die App neu starten.)" -ForegroundColor Gray
