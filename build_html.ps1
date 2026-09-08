# WOL Manager — HTML/WebView-Variante: Debug-APK bauen
# Aufruf:  .\build_html.ps1            (nur APK)
#          .\build_html.ps1 -Tests     (erst Unit-Tests, dann APK)
param(
    [switch]$Tests
)

$ErrorActionPreference = 'Stop'
$env:JAVA_HOME = 'C:\Program Files\Android\openjdk\jdk-21.0.8'
$gradle = 'C:\tools\gradle-8.7\bin\gradle.bat'
$proj = Join-Path $PSScriptRoot 'android_html'
$distDir = Join-Path $PSScriptRoot 'dist_onefile'

Push-Location $proj
try {
    if ($Tests) {
        Write-Host '== Unit-Tests ==' -ForegroundColor Cyan
        & $gradle :app:testDebugUnitTest --no-daemon --console=plain
        if ($LASTEXITCODE -ne 0) { throw 'Unit-Tests fehlgeschlagen' }
    }
    Write-Host '== APK-Build ==' -ForegroundColor Cyan
    & $gradle :app:assembleDebug --no-daemon --console=plain 2>&1 |
        Select-String -Pattern '^e:|BUILD|FAILED|warning:' | ForEach-Object { $_.Line }
    if ($LASTEXITCODE -ne 0) { throw 'APK-Build fehlgeschlagen' }

    $apk = Join-Path $proj 'app\build\outputs\apk\debug\app-debug.apk'
    if (-not (Test-Path $apk)) { throw "APK nicht gefunden: $apk" }
    New-Item -ItemType Directory -Force $distDir | Out-Null
    # Versionsname aus build.gradle.kts lesen, damit der Dateiname immer stimmt
    $gradleFile = Join-Path $proj 'app\build.gradle.kts'
    $ver = (Select-String -Path $gradleFile -Pattern 'versionName\s*=\s*"([0-9.]+)"').Matches[0].Groups[1].Value
    Get-ChildItem $distDir -Filter 'wolmanager-android-html-*-debug.apk' | Remove-Item -Force
    $out = Join-Path $distDir "wolmanager-android-html-$ver-debug.apk"
    Copy-Item $apk $out -Force
    Get-Item $out | Select-Object Name, Length, LastWriteTime
    Write-Host "OK: $out" -ForegroundColor Green
}
finally {
    Pop-Location
}
