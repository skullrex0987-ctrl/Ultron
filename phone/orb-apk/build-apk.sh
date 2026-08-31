#!/usr/bin/env bash
# Build the ULTRON Orb Android APK (Capacitor) — runs on Termux/Linux/macOS.
# Requires: Node 18+, npx (@capacitor/cli), JDK 17, Android SDK (platform 34).
# On the Poco you typically do this on a PC; the APK is then adb-install'd.
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/6] npm install (orb web assets)"
npm install --no-audit --no-fund

echo "[2/6] add android platform (skip if already added)"
npx cap add android 2>/dev/null || echo "   android platform already present"

echo "[3/6] sync ULTRON Orb logo into mipmaps"
bash android_res/sync_icons.sh

echo "[4/6] capacitor sync (copies webDir into android/app/src/main/assets)"
npx cap sync android

echo "[5/6] assemble debug APK"
cd android
./gradlew assembleDebug

echo "[6/6] done"
APK="app/build/outputs/apk/debug/app-debug.apk"
if [ -f "$APK" ]; then
  echo "APK: $(pwd)/$APK"
  echo "Install on device: adb install -r \"$APK\""
else
  echo "APK not found — check gradle output above."
  exit 1
fi
