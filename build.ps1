# ============================================================================
# Wake-on-LAN Manager - Build Script
# Version: 1.7.0 - Host Service Edition
# Date: 2026-08-17
# ============================================================================
# This script builds the application, host service, uninstaller, the installer
# helper (custom-action EXE), and the final Inno Setup GUI installer.
# Run with: .\build.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  Wake-on-LAN Manager v1.7.0 - Build Script" -ForegroundColor Cyan
Write-Host "  Host Service Edition" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- Configuration ---
$APP_NAME = "Wake-on-LAN Manager"
$APP_SPEC = "Wake-on-LAN Manager.spec"
$SERVICE_NAME = "WOL Host Service"
$SERVICE_SPEC = "wol_host_service.spec"
$UNINSTALLER_SPEC = "uninstaller.spec"
$INSTALLER_SPEC = "installer.spec"
$DIST_DIR = "dist"

# --- Step 0: Sync version across documentation ---
Write-Host "[0/8] Syncing version in docs..." -ForegroundColor Yellow
$versionResult = python update_docs_version.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Version sync failed!" -ForegroundColor Red
    exit 1
}
Write-Host $versionResult
Write-Host "  Docs synced." -ForegroundColor Green

# --- Step 1: Clean previous builds ---
Write-Host "[1/8] Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path $DIST_DIR) {
    Remove-Item -Recurse -Force $DIST_DIR
}
if (Test-Path "dist_onefile") {
    Remove-Item -Recurse -Force "dist_onefile"
}
Remove-Item -Recurse -Force "build" -ErrorAction SilentlyContinue
Write-Host "  Clean." -ForegroundColor Green

# --- Step 2: Build the main application ---
Write-Host ""
Write-Host "[2/8] Building main application..." -ForegroundColor Yellow
$appResult = pyinstaller "$APP_SPEC" --distpath $DIST_DIR --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Application build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  Application built successfully." -ForegroundColor Green

# Verify application exists
$appExe = Join-Path $DIST_DIR "$APP_NAME.exe"
if (-not (Test-Path $appExe)) {
    Write-Host "ERROR: Application executable not found at $appExe" -ForegroundColor Red
    exit 1
}

# --- Step 3: Build the host service ---
Write-Host ""
Write-Host "[3/8] Building host service..." -ForegroundColor Yellow
$serviceResult = pyinstaller "$SERVICE_SPEC" --distpath $DIST_DIR --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Host service build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  Host service built successfully." -ForegroundColor Green

# Verify host service exists (onedir layout: exe + _internal in a folder)
$serviceExe = Join-Path $DIST_DIR "$SERVICE_NAME\$SERVICE_NAME.exe"
if (-not (Test-Path $serviceExe)) {
    Write-Host "ERROR: Host service executable not found at $serviceExe" -ForegroundColor Red
    exit 1
}
$serviceInternal = Join-Path $DIST_DIR "$SERVICE_NAME\_internal"
if (-not (Test-Path $serviceInternal)) {
    Write-Host "ERROR: Host service _internal folder not found at $serviceInternal" -ForegroundColor Red
    exit 1
}
# Remove the stray bootloader exe PyInstaller leaves at the dist root
# (the real onedir exe lives in the $SERVICE_NAME folder)
$strayServiceExe = Join-Path $DIST_DIR "$SERVICE_NAME.exe"
if (Test-Path $strayServiceExe) {
    Remove-Item $strayServiceExe -Force
    Write-Host "  Removed stray $SERVICE_NAME.exe from dist root." -ForegroundColor DarkGray
}
# --- Step 3b: Build the host service (onefile variant) ---
Write-Host ""
Write-Host "[3b/8] Building host service (onefile variant)..." -ForegroundColor Yellow
$serviceOneFileResult = pyinstaller "wol_host_service_onefile.spec" --distpath "dist_onefile" --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Host service onefile build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  Host service (onefile) built successfully." -ForegroundColor Green

# Verify host service (onefile) exists
$serviceOneFileExe = Join-Path "dist_onefile" "$SERVICE_NAME.exe"
if (-not (Test-Path $serviceOneFileExe)) {
    Write-Host "ERROR: Host service onefile executable not found at $serviceOneFileExe" -ForegroundColor Red
    exit 1
}
# --- Step 4: Build the uninstaller ---
Write-Host ""
Write-Host "[4/8] Building uninstaller..." -ForegroundColor Yellow
$uninstallResult = pyinstaller "$UNINSTALLER_SPEC" --distpath $DIST_DIR --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Uninstaller build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  Uninstaller built successfully." -ForegroundColor Green

# Verify uninstaller exists
$uninstallExe = Join-Path $DIST_DIR "uninstall.exe"
if (-not (Test-Path $uninstallExe)) {
    Write-Host "ERROR: Uninstaller executable not found at $uninstallExe" -ForegroundColor Red
    exit 1
}

# --- Step 5: Build the installer helper (custom-action EXE) ---
Write-Host ""
Write-Host "[5/8] Building installer helper..." -ForegroundColor Yellow
$installerResult = pyinstaller "$INSTALLER_SPEC" --distpath $DIST_DIR --noconfirm --clean
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Installer helper build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  Installer helper built successfully." -ForegroundColor Green

# Verify installer helper exists
$installerHelperExe = Join-Path $DIST_DIR "installer.exe"
if (-not (Test-Path $installerHelperExe)) {
    Write-Host "ERROR: Installer helper not found at $installerHelperExe" -ForegroundColor Red
    exit 1
}

# --- Step 6: Compile the Inno Setup GUI installer ---
Write-Host ""
Write-Host "[6/8] Compiling Inno Setup installer..." -ForegroundColor Yellow

# Locate the Inno Setup compiler (ISCC)
$iscc = $null
$cmd = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if ($cmd) {
    $iscc = $cmd.Source
} else {
    $isccCandidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $isccCandidates) {
        if (Test-Path $c) { $iscc = $c; break }
    }
}
if (-not $iscc) {
    Write-Host "ERROR: Inno Setup compiler (ISCC) not found. Install it with:" -ForegroundColor Red
    Write-Host "  winget install --id JRSoftware.InnoSetup" -ForegroundColor Red
    exit 1
}
Write-Host "  Using ISCC: $iscc" -ForegroundColor DarkGray

# Read the app version for the installer
$appVersion = python -c "from wol_app import __version__; print(__version__)"
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($appVersion)) {
    Write-Host "ERROR: Could not determine app version." -ForegroundColor Red
    exit 1
}
Write-Host "  App version: $appVersion" -ForegroundColor DarkGray

# Compile setup.iss -> dist\Wake-on-LAN Manager Setup.exe
& $iscc "/DAppVersion=$appVersion" "setup.iss"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Inno Setup compilation failed!" -ForegroundColor Red
    exit 1
}

# Verify the GUI installer exists
$setupExe = Join-Path $DIST_DIR "Wake-on-LAN Manager WinInstaller.exe"
if (-not (Test-Path $setupExe)) {
    Write-Host "ERROR: Setup executable not found at $setupExe" -ForegroundColor Red
    exit 1
}
Write-Host "  Inno Setup installer compiled successfully." -ForegroundColor Green

# --- Step 7: Summary ---
Write-Host ""
Write-Host "[7/8] Build Summary" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

$appSize = [math]::Round((Get-Item $appExe).Length / 1MB, 2)
$serviceSize = [math]::Round((Get-Item $serviceExe).Length / 1MB, 2)
$serviceOneFileSize = [math]::Round((Get-Item $serviceOneFileExe).Length / 1MB, 2)
$uninstallSize = [math]::Round((Get-Item $uninstallExe).Length / 1MB, 2)
$setupSize = [math]::Round((Get-Item $setupExe).Length / 1MB, 2)

Write-Host "  Application:  $appExe ($appSize MB)" -ForegroundColor White
Write-Host "  Host Service (onedir):  $serviceExe ($serviceSize MB)" -ForegroundColor White
Write-Host "  Host Service (onefile): $serviceOneFileExe ($serviceOneFileSize MB)" -ForegroundColor White
Write-Host "  Uninstaller:  $uninstallExe ($uninstallSize MB)" -ForegroundColor White
Write-Host "  GUI Installer:  $setupExe ($setupSize MB)" -ForegroundColor White

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BUILD COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To install, run:" -ForegroundColor Yellow
Write-Host "  $setupExe" -ForegroundColor White
Write-Host ""
