# Build the ULTRON Orb APK — Step by Step

This guide walks through **every single step** to turn the source in this repo into
a working `app-debug.apk` you can install on your Android phone (no root required).
The orb APK is a standalone Android app that shows the ULTRON orb and, when running
on the same device as the ULTRON phone agent, links to it over `ws://127.0.0.1:8081`.

> TL;DR for Windows: `cd phone/orb-apk && .\build-apk.ps1` does everything below
> automatically (installs Node/JDK/SDK if missing). This file explains what it does.

---

## What you need (prerequisites)

| Requirement | Why | Minimum |
|---|---|---|
| A computer (Windows/macOS/Linux) | The APK is **compiled on a PC**, then installed on the phone | x86-64 recommended |
| Node.js 18+ | Builds the web orb + Capacitor | LTS |
| Java JDK 17 | Android Gradle build needs it | Temurin 17 |
| Android SDK | `aapt2`, `adb`, build-tools | platform-34 + build-tools;34.0.0 |
| `npm` / `npx` | Package + Capacitor CLI | ships with Node |
| Git | Clone the repo | any |
| (optional) `adb` | Install the APK to the phone | from SDK platform-tools |
| (optional) Android phone | Run the orb | Android 8+ |

> NOTE: The build box that generated this repo is **ARM64 (aarch64)** and **cannot**
> compile the APK (Android's `aapt2` is x86-64 only). So you MUST build on an
> x86-64 PC. That is why this guide exists — do it on your laptop.

---

## Step 0 — Open a terminal

- **Windows**: open **PowerShell** (right-click → "Run as Administrator" recommended,
  so the SDK can be installed to `C:\Android\Sdk` or similar).
- **Linux/macOS/Termux**: open your shell.

---

## Step 1 — Install Node.js LTS (if missing)

**Windows (winget):**
```
winget install OpenJS.NodeJS.LTS
```
Then **restart PowerShell** so `node`/`npm` are on PATH.

**Linux/Termux:**
```
pkg install nodejs-lts 18   # Termux
# or your distro: apt install nodejs npm
```
**Verify:**
```
node -v    # should print v18.x or later
npm -v     # should print 9.x or later
```

---

## Step 2 — Install the JDK 17 (if missing)

**Windows (winget):**
```
winget install EclipseAdoptium.Temurin.17
```
**Linux:**
```
# Debian/Ubuntu
sudo apt install openjdk-17-jdk
```
**macOS:** `brew install openjdk@17` (or download from Adoptium).

**Verify:**
```
java -version    # should mention 17
```

---

## Step 3 — Install the Android SDK + build-tools

The build script does this for you, but here are the manual steps if you prefer.

**Set the SDK location** (pick a path without spaces):
- Windows: `C:\Android\Sdk`  → set `ANDROID_HOME=C:\Android\Sdk`
- Linux/macOS: `~/Android/Sdk` → `export ANDROID_HOME=$HOME/Android/Sdk`

**Download commandline-tools** from
`https://dl.google.com/android/repository/commandlinetools-<os>-<ver>_latest.zip`,
unzip into `$ANDROID_HOME/cmdline-tools/latest`.

**Install the packages:**
```
sdkmanager --sdk_root=$ANDROID_HOME "platform-tools" "platforms;android-34" "build-tools;34.0.0"
yes | sdkmanager --sdk_root=$ANDROID_HOME --licenses
```
**Verify:**
```
$ANDROID_HOME/platform-tools/adb --version
$ANDROID_HOME/build-tools/34.0.0/aapt2 --version   # (on x86-64 this works)
```

> The one-command script (`build-apk.ps1` / `build-apk.sh`) runs Steps 1–3
> automatically and refreshes PATH after each install.

---

## Step 4 — Get the source code

**Option A — let the build script clone it:**
The script clones `https://github.com/skullrex0987-ctrl/Ultron.git` into a folder
(`~\Ultron` on Windows, `./Ultron` on Linux) and `cd`s in.

**Option B — do it yourself:**
```
git clone https://github.com/skullrex0987-ctrl/Ultron.git
cd Ultron/phone/orb-apk
```

---

## Step 5 — Install web dependencies

```
cd phone/orb-apk
npm install
```
This installs `@capacitor/core`, `@capacitor/cli`, `@capacitor/android`, and three.js.

---

## Step 6 — Sync the Capacitor Android project

The `android/` folder is **already committed** in the repo (it contains the orb
icon, the WebView config, and the gradle wrapper). You only need to sync the web
assets into it:

```
npx cap sync android
```

What this does, step by step:
1. Copies `www/` (the premium orb `index.html`) into `android/app/src/main/assets/public`.
2. Updates `capacitor.config.json` inside the native project.
3. Regenerates the plugins list.

> Do **NOT** run `npx cap add android` — the platform already exists in the repo.
> `cap add` would fail or duplicate it.

---

## Step 7 — Compile the APK (the actual build)

```
cd android
./gradlew assembleDebug        # Linux/macOS/Termux
# or on Windows:
gradlew.bat assembleDebug
```

What Gradle does, step by step:
1. Downloads the Gradle distribution (first run only).
2. Resolves dependencies (Capacitor, AndroidX).
3. Compiles the Java/Kotlin native shell.
4. Bundles the WebView assets (the orb) into the APK.
5. Signs it with the **debug** keystore (auto-generated).
6. Writes the output file.

This can take **3–10 minutes** the first time (downloading + compiling). Be patient.

---

## Step 8 — Locate the APK

On success you'll see:
```
BUILD SUCCESSFUL
```
The file is at:
```
phone/orb-apk/android/app/build/outputs/apk/debug/app-debug.apk
```

---

## Step 9 — Install it on your phone

**Via USB (recommended):**
1. On the phone: Settings → About phone → tap "Build number" 7× → enable Developer Options.
2. Developer Options → enable **USB debugging**.
3. Plug the phone in (accept the authorization prompt).
4. On the PC:
```
adb install -r phone/orb-apk/android/app/build/outputs/apk/debug/app-debug.apk
```

**Via wireless ADB (no cable, no root):**
1. Phone: Developer Options → **Wireless debugging** → enable.
2. Tap "Pair device with pairing code" → note the IP:PORT + code.
3. On the PC:
```
adb pair <phone-ip>:<pairing-port>     # enter the 6-digit code
adb connect <phone-ip>:<wireless-port>
adb install -r phone/orb-apk/android/app/build/outputs/apk/debug/app-debug.apk
```

**Or just copy the APK** to the phone and tap it in a file manager (allow "Install
from unknown sources").

---

## Step 10 — Run it

Tap the **ULTRON Orb** app icon. You'll see the animated orb HUD with:
- A title `U.L.T.R.O.N. ORB`
- Status dot (IDLE / LISTEN / THINK / SPEAK)
- TALK / GESTURES / WAKE buttons
- (If the ULTRON phone agent is running on the same device) it links via
  `ws://127.0.0.1:8081` and shows live transcripts + reacts to speech.

---

## One-command version (recommended)

**Windows PowerShell (as Admin):**
```
cd phone/orb-apk
.\build-apk.ps1
```
This automates Steps 1–9: checks/installs Node, JDK, Android SDK, clones/pulls the
repo, `npm install`, `cap sync android`, `gradlew assembleDebug`, then optionally
`adb install`s if a device is connected. Each stage is wrapped in try/catch with a
clear message if something is missing.

**Linux / macOS / Termux:**
```
cd phone/orb-apk
./build-apk.sh
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `aapt2` "cannot execute / required file not found" | You're on **ARM64** (e.g. aarch64 server, Apple Silicon with wrong arch, or Termux). Build on an **x86-64 PC**. |
| `SDK location not found` | Set `ANDROID_HOME` to your SDK path and add `platform-tools` to PATH. |
| `cap add android` errors "platform already added" | Use `npx cap sync android`, not `cap add`. |
| `gradlew: command not found` | `cd android` first, and make sure `gradlew` is executable (`chmod +x gradlew` on Linux). |
| `BUILD FAILED` on first run | Internet needed for Gradle deps. Retry; check `android/app/build.gradle` for the `applicationId` (`com.ultron.orb`). |
| `adb: device not authorized` | Accept the USB prompt on the phone; or re-run `adb pair`/`adb connect`. |
| App opens but orb is black | WebView needs internet on first load to pull three.js from the CDN; after first load it's cached. Or open in a normal browser to confirm. |
| "App not installed" | Uninstall the old copy first, or use `adb install -r`. |

---

## What's inside the APK (for the curious)

- `index.html` — the premium orb (fresnel shader core, bloom, nebula, god-rays,
  audio-reactive mouthing, state color grading).
- MediaPipe hand-gesture detection (PINCH=talk, OPEN-PALM=listen, PEACE=shot,
  THUMBS=volume, SWIPE=nav, 2-HAND=zoom).
- WebSocket client to the ULTRON phone agent at `ws://127.0.0.1:8081`.
- The Capacitor native shell wraps this in an Android WebView with
  `android.app.fullscreen = true` so it feels like a real app.

That's every step. After installing, continue with `SELF_TEST.md` on the phone to
verify the full ULTRON stack end-to-end.
