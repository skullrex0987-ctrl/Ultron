# ULTRON — BUILD LOG & STATUS (live backup = GitHub skullrex0987-ctrl/Ultron)

Protocol: RESEARCH -> MAKE -> PUSH GITHUB -> TEST -> FIX -> IMPROVE -> REPEAT.
GitHub is the live backup: every step is committed+pushed. If anything breaks,
recover with:  `cd /root/jarvis-ultron && git pull origin master`

## VERIFIED WORKING (automated, build box)
- 28 unit + E2E tests pass (`python3 -m unittest discover -s tests`):
  * agent perceives -> acts -> verifies (find "YouTube" -> tap 280,430 -> reply)
  * adb launch uses `am start` (HyperOS/Android14-safe) + known-app map
  * provider cloud auto-reroute when Ollama is down
  * full model choice: local / cloud / custom endpoint parsing
  * laptop HUD<->core WS link round-trips (port 8766)
  * phone web HUD<->agent WS link round-trips (port 8081)
  * MESH: phone pairs + relays a goal to the laptop core (handshake deadlock fixed)
  * Vosk STT routing/parse (auto Hin+Eng, file transcribe) with stub vosk
  * HUD `next build` compiles clean
- Real-process smoke: `laptop/core/main.py` listens on 8766 (HUD) + 8765 (mesh).
  `phone/agent/main_phone.py` listens on 8081 (agent) + runs local brain.
- GitHub push works (master -> main on skullrex0987-ctrl/Ultron).

## REAL BUGS FIXED THIS SESSION
1. Agent loop was hollow/shell-only -> real perceive/decide/act/verify + re-check.
2. `monkey` launch unreliable on HyperOS -> `am start -n pkg/activity` + app map.
3. Phone WebSocket server existed but was never started -> `run()` now serves.
4. Laptop `main.py` ran agent on the event loop (froze HUD) -> run_in_executor.
5. Bridge handshake DEADLOCK (server waited for hello before replying; phone
   waited for reply before sending hello) -> server ACKs `OK` first.
6. `config_phone` missing `kill_switch_file`/`max_step_hard_cap` (phone imported).
7. websockets imported at top-level (broke import w/o it) -> lazy import both sides.
8. STT/TTS were skeletons -> real Vosk (auto-lang) + Piper invocation + file mode.
9. JARVIS_ env names -> ULTRON_ (rebrand residue) across config + paths.

## CANNOT VERIFY HERE (no device/hardware on build box — you verify on real gear)
- Real webcam hand gestures (MediaPipe) on laptop + phone.
- Real Vosk mic STT (Hin+Eng) — needs model download + mic.
- Real Poco X6 Pro ADB (wireless debugging, no root) + UiAutomator dumps.
- Capacitor APK compile (no JDK/Android SDK on build box).
- Real GPU render of the premium orb shaders (compile-verified only).

## HOW TO RUN (see RUNBOOK.md for full commands)
- Laptop: `cd laptop/core && python main.py`  +  `cd hud && npm run dev`
- Phone:  `cd phone/agent && python main_phone.py`  +  `cd phone/web && uvicorn main_phone_web:app`
- Link: pair by code "ultron" (or QR/token); mesh exchanges state on connect.
- Model choice: ULTRON_MAIN_MODEL=... ; cloud: ULTRON_CLOUD_FB=1 + URL/KEY.

## PACKAGING
- `python3 package.py` -> /root/outbox/ultron-{laptop,phone,orb-apk}.zip (real zips).
- Telegram: send_telegram.py (Hermes channel, chat 1209979479 / Inkiiibot).
