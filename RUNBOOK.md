# ULTRON RUNBOOK — how to actually run it

Both apps are SEPARATE but link on LAN (full mesh). Pick per device.

## 0. Prereqs (one-time)
- Laptop: Python 3.11+, Node 18+, Ollama (`ollama pull qwen3.5:4b`), `pip install websockets`
  - Android control: `adb pair` / `adb connect PHONE_IP:PORT` (wireless debugging, no root)
  - Or double-click install: everything (venv, models, launcher) at `D:\ULTRON\START_ULTRON.bat`
- Phone (Termux): ONE LINE —
  `curl -fsSL https://raw.githubusercontent.com/skullrex0987-ctrl/Ultron/main/phone/install_termux.sh | bash`
  installs packages, repo (~/ultron), Ollama + qwen3.5:0.8b, Vosk hi/en, Piper, and the
  `ultron` command (`ultron start|test|log|stop|update`).
  - Then one-time: enable Wireless debugging in dev settings, `adb tcpip 5555`,
    `adb connect 127.0.0.1:5555` (loopback, self-control).
  - Orb app: `curl -fsSL -o ~/ultron-orb.apk https://github.com/skullrex0987-ctrl/Ultron/releases/latest/download/ULTRON-Orb-universal.apk` — install, tap ⚙, set agent URL `ws://127.0.0.1:8081`.

## 1. LAPTOP (main brain, holographic HUD)
```bash
cd laptop/core
ollama serve &                      # if not running
python main.py                     # starts brain WS on :8766 + mesh bridge
# in another terminal, run the HUD:
cd ../../hud && npm run dev         # open http://localhost:3000
```
- Orb HUD: TALK button uses browser mic (Web Speech API) -> transcript -> brain; the HUD also
  has a type box for typed input.
- Standalone voice wake (no full stack): `cd laptop && python wake_ultron.py` — say "ultron"
  and it activates the laptop mic (Vosk + sounddevice), fully offline.
- Brain: qwen3.5:4b local; auto-reroutes to cloud if configured (ULTRON_CLOUD_FB=1 + ULTRON_CLOUD_URL/KEY).

## 2. PHONE (Termux mini-brain + orb APK)
```bash
ultron start        # mini-brain qwen3.5:0.8b + WS on :8081 + mesh (installed by the one-liner)
ultron test         # on-device self-test — everything should PASS
```
- The standalone **ULTRON Orb APK** (gesture-controlled, fully offline) is the primary phone UI:
  latest universal build always at
  `https://github.com/skullrex0987-ctrl/Ultron/releases/latest/download/ULTRON-Orb-universal.apk`
- Falls back to local 0.8b when laptop unreachable (full mesh Q1 A / Q23 A).
- Voice on phone: say "ultron" to wake (offline Vosk Hin+Eng via phone/agent/voice_phone.py),
  or use the orb app's TALK button / gestures. No button needed.
- Floating widget (Kotlin): see phone/floating_widget; build APK via Capacitor in phone/orb-apk.

## 3. LINK THE TWO (mesh)
- Auto-discover on LAN; or pair by shared code / QR. On connect they exchange STATE.
- From HUD: send mesh `goal` -> other device executes. From phone: same.

## 4. CHOOSE ANY MODEL
- Local: set `ULTRON_MAIN_MODEL=qwen3.5:4b` (or `smollm:135m`, `qwen3.5:0.8b`, ...).
- Cloud: `ULTRON_CLOUD_FB=1 ULTRON_CLOUD_PROV=openrouter ULTRON_CLOUD_URL=https://openrouter.ai/api/v1 ULTRON_CLOUD_KEY=sk-... ULTRON_CLOUD_MODEL=anthropic/claude-3.5-sonnet`
- Any custom endpoint: `custom|http://host:port/v1|KEY|model-name`
- Module `laptop/core/models.py`: `choose("openrouter:gpt-4o")` -> provider.

## 5. SAFETY
- Kill-switch: `touch /tmp/ultron_kill` (laptop) / `/tmp/ultron_phone_kill` (phone) -> agent stops next step.
- Agent asks YOU for step count before every task; hard cap = 200.
- Destructive shell commands require confirm; blocked if none given.
- Audit log: laptop/core/audit.jsonl, phone ~/ultron/audit.jsonl.

## 6. VERIFIED (automated tests, build box)
- 25 unit + E2E tests pass (`python3 -m unittest discover -s tests`):
  - agent perceives->acts->verifies (find "YouTube" -> tap 280,430 -> reply)
  - adb launch uses `am start` (HyperOS-safe), known app map
  - provider cloud auto-reroute when Ollama down
  - model choice parsing (local/cloud/custom)
  - laptop + phone HUD<->brain WS link round-trips
  - HUD `next build` compiles clean
- NOT verifiable here (no device): real webcam gestures, Vosk mic, Poco ADB,
  APK compile (no JDK/SDK). Runbooks above cover your hardware.
