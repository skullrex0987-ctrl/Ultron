#!/usr/bin/env bash
# Build the ULTRON Orb Android APK (Capacitor) -- fully self-contained.
# Runs on Termux / Linux / macOS. ONE command:
#
#     bash build-apk.sh
#
# Stages (each checked, logged, aborts with a clear message on failure):
#   0. Confirms bash is running.
#   1. Verifies prerequisites (node/npm, JDK 17, Android SDK) and prints
#      exactly what is missing if anything is absent.
#   2. Clones (or pulls) https://github.com/skullrex0987-ctrl/Ultron.git
#   3. npm install in phone/orb-apk, then `npx cap sync android`
#      (the android/ Capacitor project is already committed -- we do NOT run
#       `cap add android`, we only sync).
#   4. cd android && ./gradlew assembleDebug
#   5. Copies app-debug.apk to the repo root + ./out, and optionally
#      `adb install -r` if a device is connected.
#   6. Prints SUCCESS/FAILURE with the APK path.
#
# On Termux the Android SDK is normally already provided; this script does not
# auto-install the SDK (that path is Windows-specific in build-apk.ps1) but it
# will tell you precisely which tool is missing.
set -euo pipefail

# ---- config ---------------------------------------------------------------
REPO_DIR="${REPO_DIR:-}"
SKIP_PREREQS="${SKIP_PREREQS:-0}"
LOG="$(mktemp -t ultron-build-XXXXXX.log)"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"

log()  { echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO]  $*" | tee -a "$LOG"; }
ok()   { echo "$(date '+%Y-%m-%d %H:%M:%S') [OK]    $*" | tee -a "$LOG"; }
warn() { echo "$(date '+%Y-%m-%d %H:%M:%S') [WARN]  $*" | tee -a "$LOG"; }
err()  { echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $*" | tee -a "$LOG"; }
step() { echo; echo "==> $*" | tee -a "$LOG"; }

cleanup() { local rc=$?; [ $rc -ne 0 ] && err "Build aborted (see $LOG)."; exit $rc; }
trap cleanup EXIT

# ---- 0. shell check -------------------------------------------------------
step "ULTRON Orb APK build starting (log: $LOG)"
if [ -z "${BASH_VERSION:-}" ]; then
  echo "This script requires bash. Run with: bash build-apk.sh" >&2
  exit 1
fi
ok "bash $BASH_VERSION detected."

# ---- resolve repo dir -----------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "$REPO_DIR" ]; then
  probe="$SCRIPT_DIR"
  while [ -n "$probe" ]; do
    if [ -d "$probe/.git" ]; then REPO_DIR="$probe"; break; fi
    parent="$(dirname "$probe")"
    [ "$parent" = "$probe" ] && break
    probe="$parent"
  done
  [ -z "$REPO_DIR" ] && REPO_DIR="$HOME/Ultron"
fi
mkdir -p "$REPO_DIR"
REPO_DIR="$(cd "$REPO_DIR" && pwd)"
ORB_DIR="$REPO_DIR/phone/orb-apk"
ok "Repo dir: $REPO_DIR"
ok "Orb dir : $ORB_DIR"

# ---- 1. prerequisites -----------------------------------------------------
if [ "$SKIP_PREREQS" = "1" ]; then
  warn "Skipping prerequisite checks (SKIP_PREREQS=1)."
else
  step "STAGE 1/5: Prerequisites (node, npm, JDK 17, Android SDK)"
  MISSING=()
  command -v node  >/dev/null 2>&1 || MISSING+=(node)
  command -v npm   >/dev/null 2>&1 || MISSING+=(npm)
  command -v npx   >/dev/null 2>&1 || MISSING+=(npx)
  command -v java  >/dev/null 2>&1 || MISSING+=(java)
  command -v git   >/dev/null 2>&1 || MISSING+=(git)
  if [ ! -d "$ANDROID_HOME" ] || { [ ! -x "$ANDROID_HOME/cmdline-tools/bin/sdkmanager" ] && [ ! -x "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" ]; }; then
    MISSING+=(android-sdk)
  fi
  if [ ${#MISSING[@]} -gt 0 ]; then
    err "Missing prerequisites: ${MISSING[*]}"
    err "Install them, then re-run. On Termux: pkg install nodejs-lts openjdk-17 git android-sdk"
    err "and set ANDROID_HOME + accept SDK licenses (sdkmanager --licenses)."
    exit 1
  fi
  ok "node $(node -v) | npm $(npm -v) | java $(java -version 2>&1 | head -1)"
  ok "Android SDK at $ANDROID_HOME"
fi

# ---- 2. clone / pull ------------------------------------------------------
step "STAGE 2/5: Clone / pull repository"
if [ -d "$REPO_DIR/.git" ]; then
  log "Repo present -> git pull"
  git -C "$REPO_DIR" pull --ff-only
else
  if [ -e "$REPO_DIR" ] && [ ! -d "$REPO_DIR/.git" ]; then
    err "Target $REPO_DIR exists but is not a git repo. Remove it or set REPO_DIR to a clean path."
    exit 1
  fi
  log "Cloning https://github.com/skullrex0987-ctrl/Ultron.git -> $REPO_DIR"
  git clone https://github.com/skullrex0987-ctrl/Ultron.git "$REPO_DIR"
fi
if [ ! -d "$ORB_DIR" ]; then
  err "Cloned repo has no phone/orb-apk directory. Unexpected repo layout."
  exit 1
fi
ok "STAGE 2/5 complete."

# ---- 3. npm install + cap sync --------------------------------------------
step "STAGE 3/5: npm install + cap sync android"
pushd "$ORB_DIR" >/dev/null
npm install --no-audit --no-fund
npx cap sync android
popd >/dev/null
ok "STAGE 3/5 complete."

# ---- 4. gradle assembleDebug ----------------------------------------------
step "STAGE 4/5: ./gradlew assembleDebug"
ANDROID_DIR="$ORB_DIR/android"
if [ ! -x "$ANDROID_DIR/gradlew" ]; then
  err "android/gradlew not found in the committed project."
  exit 1
fi
pushd "$ANDROID_DIR" >/dev/null
./gradlew assembleDebug --no-daemon
popd >/dev/null
ok "STAGE 4/5 complete."

# ---- 5. collect APK + optional install ------------------------------------
step "STAGE 5/5: collect APK + optional install"
APK_SRC="$ORB_DIR/android/app/build/outputs/apk/debug/app-debug.apk"
if [ ! -f "$APK_SRC" ]; then
  err "Expected APK not found at: $APK_SRC"
  exit 1
fi
OUT_DIR="$REPO_DIR/out"
mkdir -p "$OUT_DIR"
ROOT_COPY="$REPO_DIR/ultron-orb-debug.apk"
OUT_COPY="$OUT_DIR/ultron-orb-debug.apk"
cp -f "$APK_SRC" "$ROOT_COPY"
cp -f "$APK_SRC" "$OUT_COPY"
ok "APK copied to: $ROOT_COPY"
ok "APK copied to: $OUT_COPY"

if command -v adb >/dev/null 2>&1; then
  DEVICES="$(adb devices 2>/dev/null | awk 'NF && $1 != "List" && $2 == "device"')"
  if [ -n "$DEVICES" ]; then
    ok "Device detected. Installing APK ..."
    adb install -r "$ROOT_COPY" || warn "adb install reported failure (non-fatal)."
  else
    warn "No device connected -- skipping adb install."
  fi
else
  warn "adb not found -- skipping install (build still succeeded)."
fi

ok "=================================================="
ok "BUILD SUCCESS"
ok "APK: $ROOT_COPY"
ok "Size: $(du -h "$ROOT_COPY" | cut -f1)"
ok "=================================================="
