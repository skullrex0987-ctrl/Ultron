# ULTRON-ULTRON  (BUILD A — masterwork)

Local, offline-first **U.L.T.R.O.N.** assistant. Two independent apps that link
on your LAN into a full mesh:

- **LAPTOP** (Windows + RTX 5060) — main brain `qwen3.5:4b`, holographic orb HUD,
  webcam hand gestures, Hermes-style tools, Android control of your phone.
- **PHONE** (Poco X6 Pro, Termux, no root) — mini brain `qwen3.5:0.8b`, headless
  agent + small orb web HUD, Vosk STT (Hin+Eng), Piper TTS, self-control via
  ADB + Accessibility, falls back to its own brain if laptop unreachable.
- **ORB APK** — standalone Android app (Capacitor) with the orb + hand gestures.

Both brains are **offline**. Cloud (OpenRouter / TokenRouter / xKiro / OpenCode /
OpenAI) is an optional opt-in fallback toggle, never required.

## Architecture
```
 LAPTOP (qwen3.5:4b)  <--LAN mesh (pair A/B/C)-->  PHONE (qwen3.5:0.8b)
   orb HUD (Next.js)                                Termux agent (Python)
   webcam gestures                                  small orb web HUD (FastAPI)
   Hermes tools + ADB control                       Vosk + Piper + ADB self-control
        |                                                    |
        +---------- full mesh: share brain / mirror / control ----------+
```
On every connect the two brains exchange state (full mesh). If the laptop brain
is down, the phone auto-uses its own 0.8b model (Q23 A).

## Quick start — LAPTOP
    cd laptop
    python3 -m venv .venv && .venv\Scripts\activate    # Windows
    pip install ollama vosk piper  (optional, for headless)
    # install Ollama desktop, then:
    ollama pull qwen3.5:4b
    cd hud && npm install && npm run dev        # orb HUD at http://localhost:3000
    cd ../core && python main.py                # brain + bridge (ws :8766, bridge :8765)

## Quick start — PHONE (Termux)
    pkg install python clang ffmpeg
    pip install ollama vosk piper fastapi uvicorn websockets
    ollama pull qwen3.5:0.8b
    cd phone/agent && python main_phone.py
    cd ../web && python main_phone_web.py       # orb HUD at http://localhost:8080
    # one-time: adb tcpip 5555  (on the phone via Termux)

## Link the two (Q5 A: auto-discover + pair)
- Laptop shows a QR (`ultron://ip:port:token`) and a pair code (default `ultron`).
- Phone scans QR or enters the code. Both A (pair code), B (token), C (QR) supported.
- On connect: brains exchange state, you can mirror orb/agent and cross-control.

## Safety
- Full auto (Q17/21 C) but the agent **asks for step count before every task**.
- Global kill-switch file + max-step hard cap. Destructive shell cmds need confirm.
- JSONL audit log of every action in `core/audit.jsonl`.

## Providers (optional cloud fallback — config `use_cloud_fallback=1`)
Ollama (default/offline), OpenRouter, TokenRouter, xKiro, OpenCode, OpenAI.
All via one OpenAI-compatible interface in `core/providers.py`.

## Tests
    cd laptop/core && python -m unittest tests.test_core -v
    # live intent test (needs a model): set CFG.main_model then run ollama_client.py

## This build (A) status
- [x] Laptop core (config, providers, brain, tools, audit, android, perception, agent, bridge)
- [x] Laptop HUD (ULTRON orb, audio-reactive, gestures, link panel, transcript)
- [x] Phone agent (mini brain, tools, android self-control, perception, bridge client)
- [x] Phone web HUD (orb + Brahma-style gestures)
- [x] Floating widget (Kotlin overlay: tap=open, hold=talk, wake-word)
- [x] Orb APK (Capacitor: Three.js + MediaPipe, named "ULTRON Orb" + logo)
- [x] Unit tests pass; live intent test passes on qwen2.5:0.5b (CPU sandbox)
- [ ] APK compile (needs JDK+Android SDK — instructions provided, not built here)
- [ ] GitHub push (awaiting your repo access)
