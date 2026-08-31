# ULTRON Orb APK builder for Windows — self-bootstrapping.
# Checks each requirement; installs what's missing via winget/scoop, then builds.
# Run in PowerShell (as admin recommended for SDK install). From repo root.
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir

function Need($cmd){ return [string]::IsNullOrEmpty((Get-Command $cmd -ErrorAction SilentlyContinue)) }

function InstallWinget($id){
  if (Need winget) { Write-Host "winget missing — install App Installer from Microsoft Store."; exit 1 }
  winget install --accept-package-agreements --accept-source-agreements -e $id
}

# ---- [REQ 1] Node 18+ ----
if (Need node) { Write-Host "[req] Node missing -> install"; InstallWinget Microsoft.NodeJS }
else { Write-Host "[req] Node $(node -v) present" }

# ---- [REQ 2] JDK 17 ----
if (-not (Test-Path "HKLM:\SOFTWARE\JavaSoft\JDK")) {
  Write-Host "[req] JDK 17 missing -> install Microsoft.OpenJDK.17"
  InstallWinget Microsoft.OpenJDK.17
}
# point JAVA_HOME at the installed JDK
$jdk = (Get-ChildItem "C:\Program Files\Microsoft\jdk\*17*" -ErrorAction SilentlyContinue | Select-Object -First 1)
if ($jdk) { $env:JAVA_HOME = $jdk.FullName; Write-Host "[req] JAVA_HOME=$env:JAVA_HOME" }

# ---- [REQ 3] Android SDK (cmdline-tools + platform 34) ----
$androidHome = "$env:LOCALAPPDATA\Android\Sdk"
if (-not (Test-Path "$androidHome\cmdline-tools")) {
  Write-Host "[req] Android SDK missing -> installing via cmdline-tools"
  InstallWinget Google.AndroidSDK  # installs cmdline-tools + stub
}
$env:ANDROID_HOME = $androidHome
$svc = "$androidHome\cmdline-tools\latest\bin\sdkmanager.bat"
if (Test-Path $svc) {
  & $svc --sdk_root=$androidHome "platform-tools" "platforms;android-34" "build-tools;34.0.0"
}
$adb = "$androidHome\platform-tools\adb.exe"
if (Test-Path $adb) { Write-Host "[req] adb present" } else { Write-Host "[req] adb NOT found" }

# ---- [REQ 4] Capacitor CLI ----
if (Need npx) { Write-Host "npx missing (Node install failed?)"; exit 1 }
npm install -g @capacitor/cli --no-audit --no-fund 2>$null

# ---- BUILD ----
Write-Host "[1/6] npm install (orb web assets)"
npm install --no-audit --no-fund
Write-Host "[2/6] add android platform"
npx cap add android 2>$null; if ($LASTEXITCODE -ne 0) { Write-Host "   android already present" }
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
  Write-Host "Install on device: adb install -r $apk"
} else { Write-Host "APK not found — see gradle output above."; exit 1 }
