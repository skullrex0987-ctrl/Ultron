# Build the ULTRON Orb Android APK on Windows (Android Studio CLI tools).
# Prereqs: Node 18+, JDK 17, Android SDK (platform 34) on PATH; run from repo root.
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir

Write-Host "[1/6] npm install"
npm install --no-audit --no-fund

Write-Host "[2/6] add android platform"
npx cap add android 2>$null; if ($LASTEXITCODE -ne 0) { Write-Host "   android platform already present" }

Write-Host "[3/6] sync ULTRON Orb logo"
bash android_res/sync_icons.sh

Write-Host "[4/6] capacitor sync"
npx cap sync android

Write-Host "[5/6] assemble debug APK"
Set-Location android
.\gradlew.bat assembleDebug

Write-Host "[6/6] done"
$apk = "app\build\outputs\apk\debug\app-debug.apk"
if (Test-Path $apk) {
  Write-Host "APK: $(Resolve-Path $apk)"
  Write-Host "Install: adb install -r $apk"
} else {
  Write-Host "APK not found — check gradle output above."; exit 1
}
