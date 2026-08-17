# ============================================================================
# patch_setup_manifest.ps1
#
# Patches the embedded manifest of the Inno Setup installer EXE from
# level="asInvoker" to level="requireAdministrator" so that Windows shows
# the admin shield on the installer icon (like uninstall.exe).
#
# Inno Setup always writes an asInvoker manifest into Setup.exe (it elevates
# itself at runtime instead).
#
# IMPORTANT: This patch works on RAW BYTES and keeps the file length
# unchanged (the level value is padded with spaces up to the next attribute).
# Never round-trip the file through a text encoding (ASCII/UTF8) - that
# corrupts all binary data (icons, compressed payload).
#
# Usage: .\patch_setup_manifest.ps1 -SetupExe "dist\Wake-on-LAN Manager WinInstaller.exe"
# ============================================================================
param(
    [Parameter(Mandatory = $true)]
    [string]$SetupExe
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SetupExe)) {
    Write-Host "ERROR: Setup EXE not found: $SetupExe" -ForegroundColor Red
    exit 1
}

function Find-AsciiPattern {
    param([byte[]]$Data, [string]$Pattern, [int]$StartIndex)
    $p = [System.Text.Encoding]::ASCII.GetBytes($Pattern)
    $max = $Data.Length - $p.Length
    for ($i = $StartIndex; $i -le $max; $i++) {
        $match = $true
        for ($j = 0; $j -lt $p.Length; $j++) {
            if ($Data[$i + $j] -ne $p[$j]) { $match = $false; break }
        }
        if ($match) { return $i }
    }
    return -1
}

$bytes = [System.IO.File]::ReadAllBytes($SetupExe)
$origSize = $bytes.Length

# Locate: level="asInvoker" ... uiAccess
$levelIdx = Find-AsciiPattern $bytes 'level="asInvoker"' 0
if ($levelIdx -lt 0) {
    Write-Host "ERROR: Pattern level=`"asInvoker`" not found (already patched?)." -ForegroundColor Red
    exit 1
}
# Ensure it occurs exactly once
if ((Find-AsciiPattern $bytes 'level="asInvoker"' ($levelIdx + 1)) -ge 0) {
    Write-Host "ERROR: Pattern found more than once - aborting." -ForegroundColor Red
    exit 1
}

$uiIdx = Find-AsciiPattern $bytes 'uiAccess' ($levelIdx + 10)
if ($uiIdx -lt 0) {
    Write-Host "ERROR: uiAccess attribute not found after level - aborting." -ForegroundColor Red
    exit 1
}

# Region to rewrite: from the 'a' of asInvoker up to (not including) uiAccess.
# Old content:  asInvoker" + spaces
# New content:  requireAdministrator" + spaces (same total length)
$regionStart = $levelIdx + 7          # after 'level="'
$regionLen = $uiIdx - $regionStart
$newCore = [System.Text.Encoding]::ASCII.GetBytes('requireAdministrator"')

if ($regionLen -lt $newCore.Length) {
    Write-Host "ERROR: Manifest region too small ($regionLen < $($newCore.Length)) - aborting." -ForegroundColor Red
    exit 1
}

for ($k = 0; $k -lt $newCore.Length; $k++) {
    $bytes[$regionStart + $k] = $newCore[$k]
}
for ($k = $newCore.Length; $k -lt $regionLen; $k++) {
    $bytes[$regionStart + $k] = 0x20   # pad with spaces
}

if ($bytes.Length -ne $origSize) {
    Write-Host "ERROR: File size changed - aborting." -ForegroundColor Red
    exit 1
}

[System.IO.File]::WriteAllBytes($SetupExe, $bytes)

# Verify
$verify = [System.IO.File]::ReadAllBytes($SetupExe)
$vText = [System.Text.Encoding]::ASCII.GetString($verify)
if ($vText.Contains('level="requireAdministrator"') -and $verify.Length -eq $origSize) {
    Write-Host "  Manifest patched: requireAdministrator (admin shield enabled, file intact)." -ForegroundColor Green
} else {
    Write-Host "ERROR: Verification failed." -ForegroundColor Red
    exit 1
}
