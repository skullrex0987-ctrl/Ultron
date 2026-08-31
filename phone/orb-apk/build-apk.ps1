<#
  ULTRON Orb APK builder for Windows -- fully self-contained.
  ONE command on a fresh Windows machine builds the APK from scratch:

      powershell -ExecutionPolicy Bypass -File build-apk.ps1

  What it does (each stage is checked, logged, and wrapped in try/catch):
    0. Confirms it is running inside PowerShell.
    1. Installs/verifies prerequisites via winget:
         - Node.js LTS          (OpenJS.NodeJS.LTS)
         - JDK 17               (EclipseAdoptium.Temurin.17)
         - Android SDK cmdline-tools + platform-34 + build-tools;34.0.0
           (sets ANDROID_HOME, downloads cmdline-tools, unzips, sdkmanager
            installs platform-tools / platforms;android-34 / build-tools;34.0.0,
            accepts licenses)
    2. Clones (or pulls) https://github.com/skullrex0987-ctrl/Ultron.git
    3. npm install in phone/orb-apk, then `npx cap sync android`
       (the android/ Capacitor project is already committed -- we do NOT run
        `cap add android`, we only sync).
    4. cd android && gradlew.bat assembleDebug
    5. Copies app-debug.apk to the repo root + ./out, and optionally
       `adb install -r` if a device is connected.
    6. Prints clear SUCCESS / FAILURE with the APK path.

  No secrets are used or stored. Run as admin is recommended so winget/sdk
  installs land in system locations cleanly, but it works from a normal
  PowerShell window too.
#>

[CmdletBinding()]
param(
    # Where the Ultron repo should live. Leave empty to auto-detect (if this
    # script is already inside a clone) or default to ~\Ultron.
    [string]$RepoDir = "",
    # Skip prerequisite installation (use if Node/JDK/Android SDK already set up).
    [switch]$SkipPrereqs
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
$LogPath = Join-Path $env:TEMP "ultron-build-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
$Global:ULTRON_LOG = $LogPath

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$stamp [$Level] $Message"
    try { Add-Content -Path $Global:ULTRON_LOG -Value $line -Encoding UTF8 } catch {}
    switch ($Level) {
        "OK"    { Write-Host $line -ForegroundColor Green }
        "WARN"  { Write-Host $line -ForegroundColor Yellow }
        "ERROR" { Write-Host $line -ForegroundColor Red }
        "STEP"  { Write-Host ("`n==> " + $Message) -ForegroundColor Cyan }
        default { Write-Host $line }
    }
}

# Run an external command and throw on a non-zero exit code.
function Run {
    param([string]$Exe, [string[]]$ArgumentList = @())
    $cmdLine = ($Exe + " " + ($ArgumentList -join " "))
    Write-Log ">> $cmdLine" "STEP"
    & $Exe @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command exited with code $LASTEXITCODE : $cmdLine"
    }
}

# Refresh PATH from the machine + user environment (winget installs land there).
function Refresh-Env {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user    = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user;$($env:Path)"
}

function Need($cmd) {
    return [string]::IsNullOrEmpty((Get-Command $cmd -ErrorAction SilentlyContinue))
}

function Find-JavaHome {
    $roots = @(
        "$env:ProgramFiles\Eclipse Adoptium",
        "$env:ProgramFiles\Java",
        "${env:ProgramFiles(x86)}\Eclipse Adoptium",
        "${env:ProgramFiles(x86)}\Java"
    )
    foreach ($base in $roots) {
        if (Test-Path $base) {
            $jdk = Get-ChildItem $base -Directory -ErrorAction SilentlyContinue |
                   Where-Object { $_.Name -match 'jdk-17|jdk17|temurin.*17' } |
                   Sort-Object Name -Descending | Select-Object -First 1
            if ($jdk) { return $jdk.FullName }
        }
    }
    # Fallback: search for a java.exe and walk up two levels.
    $java = Get-ChildItem -Path "$env:ProgramFiles", "${env:ProgramFiles(x86)}" -Recurse -Filter java.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($java) { return (Split-Path -Parent (Split-Path -Parent $java.FullName)) }
    return $null
}

function Install-Winget($id) {
    if (Need winget) {
        throw "winget is missing. Install 'App Installer' from the Microsoft Store, then re-run."
    }
    Write-Log "Installing $id via winget ..."
    winget install --accept-package-agreements --accept-source-agreements --disable-interactivity -e $id
    if ($LASTEXITCODE -ne 0) {
        throw "winget install failed for $id (exit $LASTEXITCODE)."
    }
    Refresh-Env
}

# ---------------------------------------------------------------------------
# 0. PowerShell sanity check
# ---------------------------------------------------------------------------
Write-Log "ULTRON Orb APK build starting. Log: $LogPath" "STEP"
if ($PSVersionTable.PSVersion.Major -lt 5) {
    throw "This script requires PowerShell 5.1+ (you have $($PSVersionTable.PSVersion))."
}
Write-Log "PowerShell $($PSVersionTable.PSVersion) detected." "OK"

# ---------------------------------------------------------------------------
# Resolve repo directory (auto-detect if we are already inside a clone)
# ---------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $RepoDir) {
    $probe = $ScriptDir
    while ($probe) {
        if (Test-Path (Join-Path $probe ".git")) { $RepoDir = $probe; break }
        $parent = Split-Path -Parent $probe
        if ($parent -eq $probe) { break }
        $probe = $parent
    }
    if (-not $RepoDir) {
        $RepoDir = Join-Path $env:USERPROFILE "Ultron"
    }
}
$resolved = Resolve-Path $RepoDir -ErrorAction SilentlyContinue
if ($resolved) { $RepoDir = $resolved.Path }
if (-not $RepoDir) { $RepoDir = (New-Item -ItemType Directory -Force -Path $RepoDir).FullName }
$OrbDir = Join-Path $RepoDir "phone" "orb-apk"
Write-Log "Repo dir : $RepoDir"
Write-Log "Orb dir  : $OrbDir"

# ---------------------------------------------------------------------------
# 1. Prerequisites
# ---------------------------------------------------------------------------
if ($SkipPrereqs) {
    Write-Log "Skipping prerequisite install (SkipPrereqs set)." "WARN"
} else {
    try {
        Write-Log "STAGE 1/5: Prerequisites (Node, JDK 17, Android SDK)" "STEP"

        # --- Node.js LTS ---
        if (Need node) {
            Write-Log "Node not found -> installing OpenJS.NodeJS.LTS"
            Install-Winget "OpenJS.NodeJS.LTS"
        } else {
            Write-Log "Node present: $(node -v)" "OK"
        }

        # --- JDK 17 ---
        $javaHome = Find-JavaHome
        if (-not $javaHome) {
            Write-Log "JDK 17 not found -> installing EclipseAdoptium.Temurin.17"
            Install-Winget "EclipseAdoptium.Temurin.17"
            $javaHome = Find-JavaHome
        }
        if (-not $javaHome) { throw "Could not locate a JDK 17 install after install." }
        $env:JAVA_HOME = $javaHome
        $env:Path = "$javaHome\bin;$env:Path"
        Write-Log "JAVA_HOME = $javaHome" "OK"
        & "$javaHome\bin\java.exe" -version 2>&1 | ForEach-Object { Write-Log "  $_" }

        # --- Android SDK (cmdline-tools + platform 34 + build-tools 34.0.0) ---
        $androidHome = Join-Path $env:LOCALAPPDATA "Android\Sdk"
        $env:ANDROID_HOME = $androidHome
        $svc = Join-Path $androidHome "cmdline-tools\latest\bin\sdkmanager.bat"

        if (-not (Test-Path $svc)) {
            Write-Log "Android cmdline-tools missing -> downloading official zip"
            $tmp = Join-Path $env:TEMP "ultron_sdk_tmp"
            if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
            New-Item -ItemType Directory -Force -Path $tmp | Out-Null
            $zip = Join-Path $tmp "cmdline-tools.zip"
            $url = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
            try {
                Invoke-WebRequest -Uri $url -OutFile $zip -ErrorAction Stop
            } catch {
                Write-Log "Direct cmdline-tools download failed: $_" "WARN"
                Write-Log "Falling back to winget Google.AndroidSDK ..." "WARN"
                Install-Winget "Google.AndroidSDK"
            }
            if (-not (Test-Path $svc)) {
                if (Test-Path $zip) {
                    Expand-Archive -Path $zip -DestinationPath $tmp -Force
                    $extracted = Join-Path $tmp "cmdline-tools"
                    $destParent = Join-Path $androidHome "cmdline-tools"
                    New-Item -ItemType Directory -Force -Path $destParent | Out-Null
                    $destLatest = Join-Path $destParent "latest"
                    if (-not (Test-Path $destLatest)) {
                        Move-Item -Path $extracted -Destination $destLatest -Force
                    }
                }
            }
        }
        if (-not (Test-Path $svc)) { throw "sdkmanager.bat still missing at: $svc" }
        Write-Log "sdkmanager found: $svc" "OK"

        # Accept licenses (non-interactive: feed 'y').
        Write-Log "Accepting Android SDK licenses ..."
        $yes = "y`n" * 40
        $yes | & $svc --licenses 2>&1 | Out-Null

        # Install required packages.
        Write-Log "Installing platform-tools / platforms;android-34 / build-tools;34.0.0 ..."
        & $svc --sdk_root="$androidHome" "platform-tools" "platforms;android-34" "build-tools;34.0.0"
        if ($LASTEXITCODE -ne 0) { throw "sdkmanager install failed (exit $LASTEXITCODE)." }

        $env:Path = "$androidHome\platform-tools;$androidHome\cmdline-tools\latest\bin;$env:Path"
        Write-Log "STAGE 1/5 complete: prerequisites ready." "OK"
    } catch {
        Write-Log "PREREQ FAILURE: $_" "ERROR"
        Write-Log "What's missing: a required tool could not be installed. Open the log ($LogPath) and install it manually, or re-run as Administrator." "ERROR"
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 2. Clone or pull the repo
# ---------------------------------------------------------------------------
try {
    Write-Log "STAGE 2/5: Clone / pull repository" "STEP"
    if (-not (Need git)) {
        if (Test-Path (Join-Path $RepoDir ".git")) {
            Write-Log "Repo present -> git pull"
            Push-Location $RepoDir
            try { Run git @("pull", "--ff-only") } finally { Pop-Location }
        } else {
            if (Test-Path $RepoDir) {
                throw "Target $RepoDir exists but is not a git repo. Remove it or pass -RepoDir to a clean path."
            }
            Write-Log "Cloning https://github.com/skullrex0987-ctrl/Ultron.git -> $RepoDir"
            Run git @("clone", "https://github.com/skullrex0987-ctrl/Ultron.git", $RepoDir)
        }
    } else {
        throw "git is not installed/available on PATH."
    }
    if (-not (Test-Path $OrbDir)) {
        throw "Cloned repo has no phone/orb-apk directory. Unexpected repo layout."
    }
    Write-Log "STAGE 2/5 complete." "OK"
} catch {
    Write-Log "CLONE/PULL FAILURE: $_" "ERROR"
    Write-Log "What's missing: git, or network access to github.com, or the Ultron repo layout changed." "ERROR"
    exit 1
}

# ---------------------------------------------------------------------------
# 3. npm install + capacitor sync (android/ is already committed -> sync only)
# ---------------------------------------------------------------------------
try {
    Write-Log "STAGE 3/5: npm install + cap sync android" "STEP"
    Push-Location $OrbDir
    try {
        if (Need node) { throw "node still not on PATH after install. Restart PowerShell or check Node install." }
        Run node @("npm", "install", "--no-audit", "--no-fund")
        Run npx   @("cap", "sync", "android")
    } finally { Pop-Location }
    Write-Log "STAGE 3/5 complete." "OK"
} catch {
    Write-Log "SYNC FAILURE: $_" "ERROR"
    Write-Log "What's missing: npm dependencies or the Capacitor CLI. Check network + Node install." "ERROR"
    exit 1
}

# ---------------------------------------------------------------------------
# 4. Gradle assembleDebug
# ---------------------------------------------------------------------------
$ApkPath = $null
try {
    Write-Log "STAGE 4/5: gradlew assembleDebug" "STEP"
    $androidDir = Join-Path $OrbDir "android"
    if (-not (Test-Path (Join-Path $androidDir "gradlew.bat"))) {
        throw "android/gradlew.bat not found in the committed project."
    }
    Push-Location $androidDir
    try {
        Run ".\gradlew.bat" @("assembleDebug", "--no-daemon")
    } finally { Pop-Location }
    Write-Log "STAGE 4/5 complete." "OK"
} catch {
    Write-Log "BUILD FAILURE: $_" "ERROR"
    Write-Log "What's missing: a clean Android SDK (platform-34 + build-tools;34.0.0) or JDK 17. Check the gradle output above." "ERROR"
    exit 1
}

# ---------------------------------------------------------------------------
# 5. Locate APK, copy out, optionally install
# ---------------------------------------------------------------------------
try {
    Write-Log "STAGE 5/5: collect APK + optional install" "STEP"
    $ApkSource = Join-Path $OrbDir "android\app\build\outputs\apk\debug\app-debug.apk"
    if (-not (Test-Path $ApkSource)) {
        throw "Expected APK not found at: $ApkSource"
    }

    # Copy to repo root + ./out
    $outDir = Join-Path $RepoDir "out"
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $rootCopy = Join-Path $RepoDir "ultron-orb-debug.apk"
    $outCopy  = Join-Path $outDir  "ultron-orb-debug.apk"
    Copy-Item -Path $ApkSource -Destination $rootCopy -Force
    Copy-Item -Path $ApkSource -Destination $outCopy  -Force
    Write-Log "APK copied to: $rootCopy" "OK"
    Write-Log "APK copied to: $outCopy"  "OK"

    # Optional: adb install if a device is connected.
    $adb = Join-Path $env:ANDROID_HOME "platform-tools\adb.exe"
    if (Test-Path $adb) {
        $devices = & $adb devices 2>$null
        $connected = ($devices | Where-Object { $_ -match '\tdevice$' }).Count
        if ($connected -gt 0) {
            Write-Log "Device detected ($connected). Installing APK ..." "OK"
            & $adb install -r $rootCopy
            if ($LASTEXITCODE -eq 0) { Write-Log "adb install succeeded." "OK" }
            else { Write-Log "adb install reported failure (non-fatal)." "WARN" }
        } else {
            Write-Log "No device connected -- skipping adb install." "WARN"
        }
    } else {
        Write-Log "adb not found -- skipping install (build still succeeded)." "WARN"
    }

    Write-Log "==================================================" "OK"
    Write-Log "BUILD SUCCESS" "OK"
    Write-Log "APK: $rootCopy" "OK"
    Write-Log "Size: $([math]::Round((Get-Item $rootCopy).Length/1MB,2)) MB" "OK"
    Write-Log "==================================================" "OK"
    exit 0
} catch {
    Write-Log "COLLECT/INSTALL FAILURE: $_" "ERROR"
    Write-Log "The build likely succeeded but the APK could not be located/copied. Check: $ApkSource" "ERROR"
    exit 1
}
