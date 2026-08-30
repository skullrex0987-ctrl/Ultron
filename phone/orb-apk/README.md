# ULTRON Orb — standalone Android APK (Three.js + MediaPipe hand gestures)

A self-contained orb HUD that runs as a native Android app via Capacitor WebView.
App name: **ULTRON Orb** · Logo: holographic amber orb (generated in `android_res/`).

It shows the ULTRON orb, reacts to your voice (audio-reactive), and is
controlled by bare-hand gestures through the front camera:
  PINCH (thumb+index)  -> talk / wake
  OPEN PALM           -> toggle listen
  PEACE (✌️)          -> screenshot / snapshot
  THUMBS UP / DOWN     -> volume up / down
  SWIPE LEFT / RIGHT   -> prev / next
  2-HAND PINCH         -> zoom

It talks to the Termux agent over WebSocket (ws://<phone-ip>:8081) for brain,
STT and TTS. Fully offline-capable (Vosk + Ollama on the phone).

## Build (requires Node 18+, JDK 17, Android SDK platform 34)
    cd phone/orb-apk
    npm install
    npx cap add android        # generates ./android
    bash android_res/sync_icons.sh   # copy ULTRON Orb logo into mipmaps
    npx cap sync android
    cd android && ./gradlew assembleDebug
    # output: android/app/build/outputs/apk/debug/app-debug.apk

Install:  adb install -r android/app/build/outputs/apk/debug/app-debug.apk

> Grant CAMERA permission when prompted. The orb needs the front camera only
  for gestures; no video leaves the device.

Note: this build environment has no JDK/Android SDK, so the APK is NOT compiled
here. The project is complete and build-ready — run the commands above on your
Windows laptop (Android Studio command-line tools) or any machine with the SDK.
