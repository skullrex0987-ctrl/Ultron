# 🛡️ ULTRON

> **Your personal AI assistant. Laptop + phone, linked. Cloud-first intelligence with optional offline mode.**

[![APK Download](https://img.shields.io/badge/📱_APK-Download-success?style=for-the-badge)](https://github.com/skullrex0987-ctrl/Ultron/raw/main/releases/ultron-v1.0.0.apk)
[![Tests](https://img.shields.io/badge/✅-44_tests_passing-blue?style=for-the-badge)](tests/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)](https://python.org)

---

## 📑 Table of Contents

- [What is ULTRON?](#what-is-ultron)
- [✨ Features](#-features)
- [📱 Download APK](#-download-apk)
- [🚀 Quick Start](#-quick-start)
- [🏗️ Architecture](#️-architecture)
- [📚 Documentation](#-documentation)
- [🧠 Model Choice](#-model-choice)
- [🔗 Mesh Linking](#-mesh-linking)
- [🛡️ Safety](#️-safety)
- [📂 Project Structure](#-project-structure)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## What is ULTRON?

ULTRON is a **personal AI assistant** that runs on your own hardware. It ships as two independent apps that link into a single "mesh" over your local network:

| Component | Technology | Description |
|---|---|---|
| **🖥️ Laptop Brain** | Python + Next.js | Main AI brain with holographic orb HUD |
| **📱 Phone Agent** | Termux Python | Mini-brain with Vosk STT + Piper TTS |
| **📱 Standalone APK** | Kotlin + llama.cpp | No Termux needed, local LLM inference |

**Key principle:** ULTRON is **online-first** — it uses cloud providers (Claude, GPT, DeepSeek, OpenRouter) by default for maximum intelligence. Local Ollama is available as an **optional offline fallback**.

---

## ✨ Features

### ☁️ Multi-Provider Cloud Intelligence
- **Anthropic (Claude)** · **OpenAI (GPT)** · **DeepSeek** · **OpenRouter**
- Automatic failover between providers
- No hardcoded keys — all via environment variables

### 🔒 Optional Offline Mode
- Local Ollama models (qwen3.5:4b, qwen3.5:0.8b, smollm:135m)
- llama.cpp integration in standalone APK
- Download GGUF models (qwen3, gemma, llama, phi)

### 💻📱 Two Apps, One Mesh
- Laptop and phone link over LAN
- Full state exchange on connect
- Cross-control devices (ADB, no root)

### 🗣️ Speech In/Out
- **Laptop:** Browser mic + Web Speech API
- **Phone:** Vosk (Hindi + English) + Piper TTS
- **Wake word:** Say "ultron" — fully offline, no button

### 🎙️ Voice Activation
| Device | Wake Word | Method |
|---|---|---|
| Laptop | "ultron" | `sounddevice` + Vosk |
| Phone | "ultron" | Vosk (Hin+Eng) |
| APK | Touch OR wake word | Android SpeechRecognizer |

### ✋ Gesture-Reactive Orb
- **PINCH** → Talk
- **OPEN-PALM** → Listen
- **PEACE** → Screenshot
- **THUMBS-UP** → Volume
- **SWIPE** → Prev/Next
- **2-HAND** → Zoom

### 🧾 Structured Output + Research Mode
- Formatted, sectioned answers (lists/tables/steps)
- Research mode fetches web pages and replies with citations

### 🤖 Hermes-Style Tools
- Shell, file read/write, web fetch, ADB device control
- All sandboxed and audit-logged

### 🛑 Safety Built In
- Global kill-switch file
- Per-task step cap (max 200)
- Destructive-command confirmation
- Every action written to audit log

### 🔧 Self-Healing
- Crashes auto-restart with backoff
- Health watchdog monitors brain + mic
- Stuck-task guard aborts hung runs

---

## 📱 Download APK

### **[⬇️ Download ULTRON v1.0.0 APK](https://github.com/skullrex0987-ctrl/Ultron/raw/main/releases/ultron-v1.0.0.apk)**

| Property | Value |
|---|---|
| **Size** | 4.7 MB |
| **Min Android** | 8.0 (API 26) |
| **Target Android** | 14 (API 34) |
| **Architectures** | arm64-v8a, x86_64 |

### Install

```bash
# Via ADB
adb install ultron-v1.0.0.apk

# Or download directly on phone browser
# Settings → Security → Allow unknown sources → Install APK
```

### After Install

1. **First launch** → Grant permissions (mic, camera, storage)
2. **Download a model** → Choose from qwen3:0.6b, gemma:2b, etc.
3. **Or use cloud** → Set `OPENROUTER_API_KEY` in settings
4. **Tap the ORB** → Start talking!

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node 18+**
- **[Ollama](https://ollama.com)** (optional, for local models)

### Laptop (Main Brain + Orb HUD)

```bash
# 1) Start Ollama (optional, for local models)
ollama serve &
ollama pull qwen3.5:4b

# 2) Start the brain (WebSocket on :8766 + mesh bridge on :8765)
cd laptop/core
python main.py

# 3) In a second terminal, start the orb HUD
cd ../../hud
npm install
npm run dev          # open http://localhost:3000
```

### Phone (Termux Mini-Brain) — ONE LINE

```bash
curl -fsSL https://raw.githubusercontent.com/skullrex0987-ctrl/Ultron/main/phone/install_termux.sh | bash
```

That single command installs everything: packages, clones this repo to `~/ultron`, Python deps, Ollama + the `qwen3.5:0.8b` mini-brain, Vosk models (Hin+Eng), and Piper TTS.

Daily use:

```bash
ultron start     # launch the agent (WS :8081 + mesh)
ultron test      # on-device self-test — everything should PASS
ultron log       # live log (ultron stop / ultron update also work)
```

### Standalone APK (No Termux)

```bash
# Download APK
curl -fsSL -o ~/ultron-orb.apk https://github.com/skullrex0987-ctrl/Ultron/raw/main/releases/ultron-v1.0.0.apk

# Install
adb install -r ~/ultron-orb.apk
```

Then in the app tap **⚙** and set the agent URL to `ws://127.0.0.1:8081`.

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

  Models: Cloud (Claude/GPT/DeepSeek/OpenRouter) ── default ──▶  Local Ollama (optional)
```

---

## 📚 Documentation

| Document | Description |
|---|---|
| **[STEP_BY_STEP.md](STEP_BY_STEP.md)** | Entire project, from clone to linked mesh, in numbered steps |
| **[RUNBOOK.md](RUNBOOK.md)** | Quick run commands for each component |
| **[phone/orb-apk/APK_BUILD.md](phone/orb-apk/APK_BUILD.md)** | Every step to compile and install the APK |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | How to add tools / model providers |
| **[SECURITY.md](SECURITY.md)** | Safety model, kill-switch, report a vuln |
| **[ROADMAP.md](ROADMAP.md)** | What's done vs planned |
| **[NOTES.md](NOTES.md)** | Build log / status |

---

## 🧠 Model Choice

### Cloud Providers (Default)

| Provider | Env Var | Example Model |
|---|---|---|
| **Anthropic (Claude)** | `ANTHROPIC_API_KEY` | `claude-3.5-sonnet` |
| **OpenAI (GPT)** | `OPENAI_API_KEY` | `gpt-4o` |
| **DeepSeek** | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| **OpenRouter** | `OPENROUTER_API_KEY` | `anthropic/claude-3.5-sonnet` |

```bash
ULTRON_CLOUD_FB=1 \
ULTRON_CLOUD_PROV=openrouter \
ULTRON_CLOUD_URL=https://openrouter.ai/api/v1 \
ULTRON_CLOUD_KEY=sk-... \
ULTRON_CLOUD_MODEL=anthropic/claude-3.5-sonnet \
python laptop/core/main.py
```

### Local Models (Optional)

```bash
ULTRON_MAIN_MODEL=qwen3.5:4b      # laptop main brain
ULTRON_MINI_MODEL=qwen3.5:0.8b    # phone mini-brain
```

### Supported Models for APK

| Model | Size | RAM Needed | Speed (SD8G2) |
|---|---|---|---|
| qwen3:0.6b | ~0.5GB | 2GB | ~30 t/s |
| qwen2.5:0.5b | ~0.4GB | 2GB | ~35 t/s |
| gemma:2b | ~1.5GB | 3GB | ~20 t/s |
| qwen3:0.8b | ~0.7GB | 2.5GB | ~25 t/s |
| qwen3:1.7b | ~1.2GB | 3GB | ~15 t/s |
| llama3.2:1b | ~0.8GB | 2.5GB | ~20 t/s |
| phi3.5:mini | ~2.5GB | 4GB | ~10 t/s |

---

## 🔗 Mesh Linking

Both apps are separate processes that discover and pair on your LAN.

1. **Discover** — ULTRON uses mDNS (`_ultron._tcp.local.`) to find peers on the same network automatically.
2. **Pair** — three methods are supported:
   - **(A)** shared **pair code** (default `ultron`, override with `ULTRON_PAIR_CODE`),
   - **(B)** a **token**, or
   - **(C)** a **QR code** shown by the laptop (`ultron://ip:port:token`).
3. **Connect** — on connect, the two brains exchange state. You can now:
   - mirror the orb/agent between devices,
   - send a **goal** from one HUD and have the other device execute it,
   - let the laptop control the phone over ADB (wireless, no root).

If the laptop brain goes down, the phone transparently falls back to its own `0.8b` model and keeps operating.

---

## 🛡️ Safety

| Feature | Description |
|---|---|
| **Kill-switch** | Create `/tmp/ultron_kill` → agent stops immediately |
| **Step cap** | Max 200 steps per task (hard ceiling) |
| **Destructive guards** | `rm -rf`, `mkfs`, `dd if=`, `format`, `shutdown`, `reboot` blocked without confirmation |
| **Audit log** | Every action written to `audit.jsonl` |
| **File sandbox** | `ULTRON_FS_ROOT` restricts file access |
| **SSRF protection** | Web fetch blocks private/loopback addresses |
| **HMAC integrity** | Audit log entries signed with HMAC-SHA256 |

See **[SECURITY.md](SECURITY.md)** for the full safety model.

---

## 📂 Project Structure

```
UltrON/
├── laptop/
│   └── core/                 # Laptop "brain"
│       ├── main.py           # entry: brain WS :8766 + mesh bridge :8765
│       ├── agent.py          # perceive → decide → act → verify loop
│       ├── models.py         # model selection (local / cloud / custom)
│       ├── providers.py      # pluggable LLM layer (7 providers)
│       ├── tools.py          # Hermes-style tools (shell, file, web, adb…)
│       ├── bridge.py         # mesh bridge (discover / pair / relay)
│       ├── android_control.py# ADB device control (no root)
│       ├── perception.py     # screen/window perception
│       ├── stt_tts.py        # Vosk + Piper
│       ├── audit.py          # HMAC-signed audit logging
│       ├── config.py         # configuration
│       ├── memory.py         # persistent personal memory
│       ├── google_workspace.py # Gmail/Calendar/Drive/Docs/Sheets
│       ├── desktop_automation.py # Window/app control
│       └── proactive_engine.py # Continuous observation
│   └── hud/                  # Next.js holographic orb HUD
├── phone/
│   ├── agent/                # Termux mini-brain (Python)
│   ├── web/                  # Phone web orb HUD
│   ├── floating_widget/      # Kotlin overlay
│   └── orb-apk/              # Standalone Android APK
│       ├── android/          # Android project with llama.cpp
│       ├── app/build/outputs/apk/debug/app-debug.apk
│       └── build-apk.sh / build-apk.ps1
├── hud/                      # Next.js holographic orb HUD
├── tests/                    # 44 tests (unit + E2E + mesh)
├── releases/                 # APK downloads
│   └── ultron-v1.0.0.apk
├── docs/                     # Documentation
├── RUNBOOK.md                # Quick run commands
├── STEP_BY_STEP.md           # Full setup guide
├── CONTRIBUTING.md           # How to contribute
├── SECURITY.md               # Safety model
├── ROADMAP.md                # What's done vs planned
├── NOTES.md                  # Build log
├── README.md                 # This file
└── LICENSE                   # MIT
```

---

## 🤝 Contributing

Pull requests are welcome! See **[CONTRIBUTING.md](CONTRIBUTING.md)** for how to:

- Add a tool
- Add a model provider
- Code style
- Run the test suite

---

## 🗺️ Roadmap

What's done and what's next is tracked in **[ROADMAP.md](ROADMAP.md)**.

| Status | Feature |
|---|---|
| ✅ | Laptop brain + orb HUD |
| ✅ | Phone mini-brain + web HUD |
| ✅ | Standalone APK with llama.cpp |
| ✅ | Multi-provider cloud (Claude/GPT/DeepSeek/OpenRouter) |
| ✅ | Local Ollama + GGUF models |
| ✅ | Mesh linking (mDNS/pair-code/QR) |
| ✅ | Voice activation (wake word) |
| ✅ | Gesture-reactive orb |
| ✅ | Self-healing subsystems |
| ✅ | Persistent personal memory |
| ✅ | Google Workspace integration |
| ✅ | Desktop automation |
| ✅ | Proactive assistant engine |
| 🔜 | Encrypted mesh pairing |
| 🔜 | Plugin system |
| 🔜 | iOS orb |

---

## 📄 License

Released under the **MIT License** — see the [LICENSE](LICENSE) file.

Copyright © 2026 skullrex0987-ctrl.

---

<p align="center">
  <b>ULTRON — Your personal AI assistant.</b><br>
  Laptop + phone, linked. Cloud-first intelligence with optional offline mode.<br>
  <br>
  <a href="https://github.com/skullrex0987-ctrl/Ultron/raw/main/releases/ultron-v1.0.0.apk">📱 Download APK</a> ·
  <a href="STEP_BY_STEP.md">📖 Get Started</a> ·
  <a href="SECURITY.md">🛡️ Security</a> ·
  <a href="ROADMAP.md">🗺️ Roadmap</a>
</p>