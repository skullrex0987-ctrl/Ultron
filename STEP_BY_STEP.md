# ULTRON — Step by Step (whole project)

A plain, ordered walkthrough of the **entire** ULTRON system: what it is, how to
run the laptop brain + HUD, how to run the phone brain + orb, how to link the two,
and how to build the APK. Each step is numbered. Do them in order.

ULTRON is a **fully offline** personal AI assistant that runs on your laptop AND your
phone, and links the two over your local network. No cloud or API keys required.

---

## Part 0 — What you'll have when done
- A laptop "brain" (qwen3.5:4b via Ollama) with a cinematic 3D orb HUD you can talk to.
- A phone "mini-brain" (qwen3.5:0.8b via Ollama in Termux) with its own orb + the
  standalone ULTRON Orb APK.
- The two linked: share the brain, mirror state, cross-control over LAN.
- Screen perception (OCR), offline STT (Hindi+English), and TTS.

---

## Part 1 — Prerequisites (both devices)
1. **Ollama** installed on the laptop (https://ollama.com) and on the phone's Termux.
2. Pull the models:
   - Laptop: `ollama pull qwen3.5:4b`
   - Phone (Termux): `ollama pull qwen3.5:0.8b`
3. **Node.js 18+** on the laptop (for the HUD) and on the PC that builds the APK.
4. **Python 3.10+** on both the laptop and the phone (Termux).
5. (Phone) **Termux** from F-Droid, plus `termux-api` and the `adb` wireless
   debugging enabled in Developer Options.

---

## Part 2 — Laptop brain + HUD

6. Clone the repo:
   ```
   git clone https://github.com/skullrex0987-ctrl/Ultron.git
   cd Ultron
   ```
7. Install laptop Python deps:
   ```
   cd laptop/core
   pip install websockets pytesseract pillow   # (+ any your OS needs)
   ```
8. Start the brain (it opens a WebSocket for the HUD + the mesh bridge):
   ```
   python main.py
   ```
   You should see it listening on port **8766** (HUD) and **8765** (mesh).
9. In a second terminal, start the HUD (the orb):
   ```
   cd ../../hud
   npm install
   npm run dev
   ```
   Open the printed `http://localhost:3000` URL. You'll see the ULTRON orb.
10. Click **TALK** (your browser asks mic permission) *or* type in the HUD **type box**,
    speak/type, and the orb thinks, replies, and speaks back (browser TTS). You can also just
    say the wake word **"ultron"** out loud and the brain starts listening on its own (offline,
    Vosk + `sounddevice` — no button). For a quick shell wake **without** the whole stack, run:
    ```bash
    cd laptop
    python wake_ultron.py
    ```
    Done — laptop side works.

---

## Part 3 — Phone mini-brain + orb

11. On the phone, open Termux and clone the repo:
    ```
    git clone https://github.com/skullrex0987-ctrl/Ultron.git
    cd Ultron/phone
    ```
12. Install Termux Python deps:
    ```
    pip install websockets
    ```
13. (Optional but recommended) run the self-test to confirm your device:
    ```
    cd agent
    python selftest_phone.py
    ```
    Fix anything it flags (Vosk models, Piper, adb, Ollama).
14. Start the phone brain (it starts its own orb WebSocket on **8081**):
    ```
    cd ../agent
    python main_phone.py
    ```
15. In a browser on the phone, run the web orb HUD:
    ```
    cd ../web
    pip install fastapi uvicorn websockets
    uvicorn main_phone_web:app --host 0.0.0.0 --port 8080
    ```
    Open `http://127.0.0.1:8080` on the phone → you see the premium orb. On the phone HUD you
    can **type** in the new type box *or* say the wake word **"ultron"** (offline, Vosk
    Hindi+English via `phone/agent/voice_phone.py`) to start voice input hands-free. The
    standalone **APK** has the same type box + wake-word.

---

## Part 4 — Link the two devices (mesh)

16. Make sure both the laptop and phone are on the **same Wi-Fi/LAN**.
17. On the laptop brain, the mesh bridge auto-discovers the phone. Pair with the
    code `ultron` (or scan the QR / use the token printed by the phone).
18. Once paired, a goal you speak to the laptop can be **delegated to the phone**
    (e.g. "open YouTube on the phone"), and state is mirrored both ways.
19. Verify the link: the laptop log will show the phone as `linked: True`, and the
    phone log shows `discover laptop: True`.

---

## Part 5 — Build the Android APK (standalone orb)

20. On an **x86-64 PC** (NOT the aarch64 build box, NOT the phone), follow
    `phone/orb-apk/APK_BUILD.md` — it is the full step-by-step. Short version:
    ```
    cd phone/orb-apk
    .\build-apk.ps1        # Windows  (or ./build-apk.sh on Linux/macOS)
    # → app/build/outputs/apk/debug/app-debug.apk
    adb install -r app/build/outputs/apk/debug/app-debug.apk
    ```
21. Open the **ULTRON Orb** app on the phone. If the phone agent (step 14) is
    running, the orb links to it over `ws://127.0.0.1:8081`.

---

## Part 6 — Verify & safety

22. Run the automated tests any time:
    ```
    cd Ultron
    python3 -m unittest discover -s tests
    ```
23. **Kill-switch**: create `/tmp/ultron_kill` on either device and the agent stops
    immediately. Delete it to resume.
24. Read `SECURITY.md` (offline-by-default, no keys) and `ROADMAP.md` (what's done
    vs planned).

---

## File map (where everything lives)
- `laptop/core/` — Python brain, agent loop, Android control, mesh bridge, STT/TTS.
- `laptop/hud/` — Next.js 3D orb HUD (`lib/orbVisuals.ts` is the premium orb).
- `phone/agent/` — Termux mini-brain, tools, bridge client, self-test.
- `phone/web/` — phone web orb HUD (FastAPI + three.js).
- `phone/orb-apk/` — Capacitor standalone APK (the orb app) + build scripts + `APK_BUILD.md`.
- `tests/` — unit + e2e + mesh + WS tests.
- `RUNBOOK.md` — quick run commands. `CONTRIBUTING.md` — how to extend. `NOTES.md` — build log.

That's the whole project, step by step.
