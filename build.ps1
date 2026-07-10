# ============================================================================
# Wake-on-LAN Manager - Build Script
# ============================================================================
# This script builds the application, uninstaller, and final installer.
# Run with: .\build.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Wake-on-LAN Manager - Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- Configuration ---
$APP_NAME = "Wake-on-LAN Manager"
$APP_SPEC = "Wake-on-LAN Manager.spec"
$UNINSTALLER_SPEC = "uninstaller.spec"
$INSTALLER_SPEC = "installer.spec"
$DIST_DIR = "dist"

# --- Step 1: Clean previous builds ---
Write-Host "[1/5] Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path $DIST_DIR) {
    Remove-Item -Recurse -Force $DIST_DIR
}
Remove-Item -Recurse -Force "build" -ErrorAction SilentlyContinue
Write-Host "  Clean." -ForegroundColor Green

# --- Step 2: Build the main application ---
Write-Host ""
Write-Host "[2/5] Building main application..." -ForegroundColor Yellow
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

# --- Step 3: Build the uninstaller ---
Write-Host ""
Write-Host "[3/5] Building uninstaller..." -ForegroundColor Yellow
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

# --- Step 4: Build the installer ---
Write-Host ""
Write-Host "[4/5] Building installer..." -ForegroundColor Yellow
$installerResult = pyinstaller "$INSTALLER_SPEC" --distpath $DIST_DIR --noconfirm --clean
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Installer build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  Installer built successfully." -ForegroundColor Green

# Verify installer exists
$installerExe = Join-Path $DIST_DIR "Wake-on-LAN Manager Installer.exe"
if (-not (Test-Path $installerExe)) {
    Write-Host "ERROR: Installer executable not found at $installerExe" -ForegroundColor Red
    exit 1
}

# --- Step 5: Summary ---
Write-Host ""
Write-Host "[5/5] Build Summary" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

$appSize = [math]::Round((Get-Item $appExe).Length / 1MB, 2)
$uninstallSize = [math]::Round((Get-Item $uninstallExe).Length / 1MB, 2)
$installerSize = [math]::Round((Get-Item $installerExe).Length / 1MB, 2)

Write-Host "  Application:  $appExe ($appSize MB)" -ForegroundColor White
Write-Host "  Uninstaller:  $uninstallExe ($uninstallSize MB)" -ForegroundColor White
Write-Host "  Installer:    $installerExe ($installerSize MB)" -ForegroundColor White

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BUILD COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To install, run:" -ForegroundColor Yellow
Write-Host "  $installerExe" -ForegroundColor White
Write-Host ""
Write-Host "Note: Run as Administrator for installation." -ForegroundColor Yellow
Write-Host ""
