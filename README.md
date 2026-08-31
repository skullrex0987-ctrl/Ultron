# 🛡️ ULTRON

> **Offline-first AI assistant. Two linkable apps — your laptop and your phone — that work together on your own LAN. No cloud required.**

ULTRON is a privacy-minded personal AI assistant you run **entirely on your own
hardware**. It ships as two independent apps that you can link into a single
"mesh" over your local network:

- **Laptop app** — a Python "brain" (`qwen3.5:4b` via Ollama) plus a Next.js
  holographic **orb HUD** you talk to in the browser.
- **Phone app** — a lighter Termux Python "mini-brain" (`qwen3.5:0.8b`) plus a
  small web orb HUD, Vosk speech-to-text (Hindi + English), Piper text-to-speech,
  and self-control of the phone via ADB + Accessibility. A standalone **Android
  APK** (Capacitor) bundles the orb too.

Everything is **offline by default** — your data and your model never leave your
devices. Cloud providers (OpenRouter, OpenAI, etc.) are an *optional, opt-in*
fallback, never a requirement.

---

## ✨ Features

- 🔒 **Fully offline** — local models via Ollama; no account, no API key, no telemetry.
- 💻📱 **Two apps, one mesh** — laptop and phone link over LAN into a full mesh:
  share a brain, mirror the orb, and cross-control devices.
- 🧠 **Full model choice** — any local Ollama model, or any OpenAI-compatible
  cloud/custom endpoint (OpenRouter, TokenRouter, xKiro, OpenCode, OpenAI).
- 🗣️ **Speech in/out** — browser mic + Web Speech on laptop; Vosk (Hin+Eng) +
  Piper on phone.
- ✋ **Gesture-reactive orb** — premium audio/gesture-reactive orb on laptop,
  phone-web, and the standalone APK.
- 🤖 **Hermes-style tools** — shell, file read/write, web fetch, and ADB device
  control, all sandboxed and audit-logged.
- 🪢 **Self-healing link** — if the laptop brain is down, the phone auto-falls
  back to its own 0.8b model.
- 🛑 **Safety built in** — global kill-switch file, per-task step cap, and
  destructive-command confirmation. Every action is written to an audit log.
- 📦 **Build your own APK** — `phone/orb-apk/build-apk.sh` / `build-apk.ps1`.

---

## 🏗️ Architecture

```
                         LAN MESH  (mDNS discover / pair-code / QR)
                                    │  full state exchange
                                    ▼
  ┌─────────────────────────────┐            ┌─────────────────────────────┐
  │  LAPTOP  (brain: qwen3.5:4b)│            │  PHONE  (mini: qwen3.5:0.8b) │
  │                             │            │                             │
  │  laptop/core/main.py        │  ◀───────▶ │  phone/agent/main_phone.py  │
  │   • brain loop (WS :8766)   │   pair A/B │   • mini-brain (WS :8081)   │
  │   • mesh bridge  (WS :8765) │   /C + QR  │   • mesh client             │
  │   • tools / providers       │            │   • tools / self-control    │
  │                             │            │                             │
  │  hud/  (Next.js orb HUD)   │            │  phone/web/  (orb web HUD)  │
  │   → http://localhost:3000   │            │   → http://<phone>:8080     │
  │   webcam gestures, mic      │            │   Vosk + Piper + ADB        │
  └─────────────────────────────┘            └─────────────────────────────┘
           │                                          │
           └── ADB control of phone (wireless, no root) ┘
                  + standalone Android APK: phone/orb-apk

  Models: Ollama (local, default)  ── optional opt-in ──▶  Cloud / custom endpoint
```

On every connect the two brains exchange state (full mesh). If the laptop brain
is unreachable, the phone automatically uses its own `0.8b` model so it keeps
working.

---

## 🚀 Quick Start

> Prereqs (one time): **Python 3.11+**, **Node 18+**, and **[Ollama](https://ollama.com)**.
> `pip install websockets` for the laptop brain.

### Laptop (main brain + orb HUD)

```bash
# 1) start Ollama with the main model (skip if already running)
ollama serve &
ollama pull qwen3.5:4b

# 2) start the brain (WebSocket on :8766 + mesh bridge on :8765)
cd laptop/core
python main.py

# 3) in a second terminal, start the orb HUD
cd ../../hud
npm install
npm run dev          # open http://localhost:3000
```

The HUD's **TALK** button uses your browser mic (Web Speech API) → transcript → brain.

### Phone (Termux mini-brain + web orb + floating widget)

```bash
# in Termux:
pkg install python clang ffmpeg android-tools
pip install websockets fastapi uvicorn vosk piper
ollama pull qwen3.5:0.8b          # if you run Ollama on the phone

# 1) start the mini-brain
cd phone/agent
python main_phone.py              # WS on :8081 + mesh

# 2) in another Termux session, start the web orb HUD
cd ../web
python -m uvicorn main_phone_web:app --host 0.0.0.0 --port 8080
# open http://<phone-ip>:8080 in the phone browser

# one-time, for self-control via ADB:
adb tcpip 5555
adb connect 127.0.0.1:5555        # loopback, no root required
```

The Kotlin **floating widget** (`phone/floating_widget`) can be built separately:
tap = open, hold = talk, wake-word ready.

> 💡 Full, copy-paste commands (incl. cloud/env wiring and Android wireless
> debugging) live in **[RUNBOOK.md](RUNBOOK.md)**.

---

## 🔗 Linking the two devices (mesh)

Both apps are separate processes that discover and pair on your LAN.

1. **Discover** — ULTRON uses mDNS (`_ultron._tcp.local.`) to find peers on the
   same network automatically.
2. **Pair** — three methods are supported:
   - **(A)** shared **pair code** (default `ultron`, override with `ULTRON_PAIR_CODE`),
   - **(B)** a **token**, or
   - **(C)** a **QR code** shown by the laptop (`ultron://ip:port:token`).
   The phone scans the QR or enters the code.
3. **Connect** — on connect, the two brains exchange state. You can now:
   - mirror the orb/agent between devices,
   - send a **goal** from one HUD and have the other device execute it,
   - let the laptop control the phone over ADB (wireless, no root).

If the laptop brain goes down, the phone transparently falls back to its own
`0.8b` model and keeps operating.

---

## 🧠 Model choice

ULTRON runs **any** model. Nothing here requires the internet.

**Local (default, offline):**
```bash
ULTRON_MAIN_MODEL=qwen3.5:4b      # laptop main brain
ULTRON_MINI_MODEL=qwen3.5:0.8b    # phone mini-brain
# any Ollama model works: smollm:135m, qwen3.5:0.8b, ...
```

**Optional cloud / custom fallback (opt-in only):**
```bash
ULTRON_CLOUD_FB=1 \
ULTRON_CLOUD_PROV=openrouter \
ULTRON_CLOUD_URL=https://openrouter.ai/api/v1 \
ULTRON_CLOUD_KEY=sk-... \
ULTRON_CLOUD_MODEL=anthropic/claude-3.5-sonnet \
python laptop/core/main.py
```
- Supported presets: **Ollama** (default/offline), **OpenRouter**,
  **TokenRouter**, **xKiro**, **OpenCode**, **OpenAI**.
- **Any custom endpoint**: `custom|http://host:port/v1|KEY|model-name`.
- Selection logic lives in `laptop/core/models.py` (`choose("openrouter:gpt-4o")` →
  provider) and the OpenAI-compatible layer in `laptop/core/providers.py`.

---

## 📱 Build the Android APK

The standalone **ULTRON Orb** app (Capacitor: Three.js + MediaPipe) is in
`phone/orb-apk/`. Build scripts are provided for both shells:

- `phone/orb-apk/build-apk.sh` — Linux / macOS / Termux
- `phone/orb-apk/build-apk.ps1` — Windows (PowerShell)

Requirements: **Node 18+**, `npx @capacitor/cli`, **JDK 17**, **Android SDK**
(platform 34).

```bash
cd phone/orb-apk
./build-apk.sh          # (or: .\build-apk.ps1 on Windows)
# → app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The script installs web assets, syncs the ULTRON Orb logo into the mipmaps, runs
`capacitor sync`, and assembles the debug APK.

---

## 📂 Project structure

```
jarvis-ultron/
├── laptop/
│   └── core/                 # Laptop "brain"
│       ├── main.py           # entry: brain WS :8766 + mesh bridge :8765
│       ├── agent.py          # perceive → decide → act → verify loop
│       ├── models.py         # model selection (local / cloud / custom)
│       ├── providers.py      # pluggable OpenAI-compatible LLM layer
│       ├── tools.py          # Hermes-style tools (shell, file, web, adb…)
│       ├── bridge.py         # mesh bridge (discover / pair / relay)
│       ├── android_control.py# ADB device control (no root)
│       ├── perception.py     # screen/window perception
│       ├── stt_tts.py        # Vosk + Piper
│       ├── audit.py / audit.jsonl
│       └── config.py
│   └── hud/                  # (legacy placeholder — HUD is at repo root /hud)
├── hud/                      # Next.js holographic orb HUD → npm run dev :3000
│   ├── app/  components/  docs/
├── phone/
│   ├── agent/                # Termux mini-brain (Python)
│   │   ├── main_phone.py     # mini-brain qwen3.5:0.8b + WS :8081 + mesh
│   │   ├── bridge_client.py  tools_phone.py  config_phone.py  …
│   ├── web/                  # small orb web HUD → uvicorn :8080
│   │   └── main_phone_web.py
│   ├── floating_widget/      # Kotlin overlay (tap=open, hold=talk)
│   └── orb-apk/              # Capacitor standalone Android app (the orb)
│       ├── build-apk.sh / build-apk.ps1
│       ├── android/  www/  index.html  capacitor.config.json
├── core/                     # shared/legacy source scaffold
├── tests/                    # 28 unit + E2E tests
│   ├── test_core.py  test_e2e.py  test_mesh.py  test_laptop_ws.py
│   └── test_perception.py  test_stt.py
├── package.py                # zips laptop/phone/orb-apk bundles
├── send_telegram.py          # optional notify helper
├── RUNBOOK.md                # exact run commands
├── NOTES.md                  # build log & verification status
├── README.md
└── LICENSE                   # MIT — see file
```

---

## 🛡️ Safety / kill-switch

ULTRON is built to be safe to run on your own machines:

- **Offline by default** — no keys, no accounts, no network calls unless you opt in.
- **Kill-switch** — create an empty file and the agent stops at its next step:
  ```bash
  touch /tmp/ultron_kill          # laptop
  touch /tmp/ultron_phone_kill    # phone
  ```
  Path is overridable via the `ULTRON_KILL` env var.
- **Step cap** — the agent asks you for a step count before every autonomous task,
  and there is a hard ceiling of **200 steps** that cannot be exceeded.
- **Destructive guards** — commands like `rm -rf`, `mkfs`, `dd if=`, `format`,
  `shutdown`, `reboot`, `chmod -R`, `curl | sh`, `wget | sh` are **blocked unless
  explicitly confirmed**.
- **Audit log** — every action is appended to a JSONL log:
  `laptop/core/audit.jsonl` (laptop) and `~/ultron/audit.jsonl` (phone).

See **[SECURITY.md](SECURITY.md)** for the full safety model and how to report a
vulnerability.

---

## 🤝 Contributing

Pull requests are welcome! Whether it's a new tool, a new model provider, a bug
fix, or docs — see **[CONTRIBUTING.md](CONTRIBUTING.md)** for how to:

- add a tool,
- add a model provider,
- code style, and
- run the test suite.

---

## 🗺️ Roadmap

What's done and what's next is tracked in **[ROADMAP.md](ROADMAP.md)** (a
user-friendly mirror of `NOTES.md`).

---

## 📄 License

Released under the **MIT License** — see the [LICENSE](LICENSE) file.
Copyright © 2026 skullrex0987-ctrl.

---

<p align="center">
  <sub>ULTRON — your offline AI assistant. Laptop + phone, linked. No cloud required.</sub>
</p>
