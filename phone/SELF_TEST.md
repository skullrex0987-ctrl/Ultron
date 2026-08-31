# ULTRON — On-Device Self-Test (you run this on real gear)

The build box has NO phone/mic/webcam/GPU, so these were code-only. Run them
on your Poco X6 Pro (Termux) and Windows laptop to confirm the real thing.

## PHONE (Poco X6 Pro, Termux) — `python phone/agent/selftest_phone.py`
Auto-checks and prints PASS/FAIL:
- [ ] adb wireless loopback (self-control, no root)
- [ ] Vosk Hin+Eng models downloaded
- [ ] Piper TTS present
- [ ] Ollama mini brain `qwen3.5:0.8b` ready
- [ ] agent WebSocket :8081 up
- [ ] orb web HUD :8080 serving

Fix any FAIL, re-run. When all PASS: `python phone/agent/main_phone.py`.

## PHONE manual checks (with your hands/voice)
- [ ] Orb HUD opens in phone browser (`http://127.0.0.1:8080`) and animates.
- [ ] Floating widget shows; TAP opens orb HUD; HOLD triggers listen.
- [ ] Say "ultron open youtube" -> phone unlocks (if locked) -> opens YouTube.
- [ ] Reply is spoken (Piper) and the orb "mouths" (audio-reactive).
- [ ] Front-camera gesture: PINCH = talk, OPEN PALM = listen, PEACE = screenshot.

## LAPTOP (Windows + RTX 5060)
- [ ] `ollama serve` running; `qwen3.5:4b` pulled.
- [ ] `python laptop/core/main.py` -> HUD WS :8766 + mesh :8765 listening.
- [ ] `cd hud && npm run dev` -> orb HUD at http://localhost:3000.
- [ ] TALK button uses mic (Web Speech API) -> transcript -> brain thinks -> orb speaks.
- [ ] Pair with phone: same LAN, code "ultron" (or QR/token). Mesh links, state mirrors.

## MESH
- [ ] Phone shows as linked in laptop HUD; laptop shows in phone HUD.
- [ ] Send a goal from either side -> other device executes + reports back.

## APK (ULTRON Orb)
- [ ] `cd phone/orb-apk && bash build-apk.sh` (or `build-apk.ps1` on Windows —
      it auto-installs Node/JDK/Android SDK if missing).
- [ ] `adb install -r android/app/build/outputs/apk/debug/app-debug.apk`.
- [ ] Grant CAMERA. Orb reacts to gestures; talks to Termux agent via WS.

## SAFETY
- [ ] Kill-switch: `touch /tmp/ultron_kill` (laptop) / `/tmp/ultron_phone_kill`
      (phone) stops the agent at the next step.
- [ ] Agent asks YOU for step count before each task; hard cap 200.
- [ ] Destructive shell commands need confirm; blocked if none given.

If a check FAILs, the exact reason is printed — fix it, re-run the script.
