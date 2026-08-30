#!/usr/bin/env bash
# Places generated mipmaps into the Capacitor Android project after `npx cap add android`.
# Run:  bash android_res/sync_icons.sh   (from phone/orb-apk)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AND="$ROOT/android/app/src/main/res"
[ -d "$AND" ] || { echo "Run 'npx cap add android' first."; exit 1; }
declare -A M=( [mdpi]=48 [hdpi]=72 [xhdpi]=96 [xxhdpi]=144 [xxxhdpi]=192 )
for d in "${!M[@]}"; do
  mkdir -p "$AND/mipmap-$d" "$AND/drawable-$d"
  cp "$ROOT/android_res/ic_launcher_$d.png" "$AND/mipmap-$d/ic_launcher.png"
  cp "$ROOT/android_res/ic_foreground_$d.png" "$AND/mipmap-$d/ic_launcher_foreground.png"
done
cat > "$AND/mipmap-anydpi-v26/ic_launcher.xml" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
  <background android:drawable="@color/ic_launcher_background"/>
  <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
</adaptive-icon>
XML
mkdir -p "$AND/mipmap-anydpi-v26" "$AND/values"
echo '<resources><color name="ic_launcher_background">#000000</color></resources>' > "$AND/values/ic_launcher_background.xml"
echo "Icons synced into $AND"
