# Roadmap — ULTRON

A personal, fully-offline AI assistant that runs on your laptop **and** your phone,
and links the two over your local network. Status below is honest: ✅ verified,
🟡 code-complete but needs your hardware to confirm, ⬜ not started.

## ✅ Done & verified (automated, on the build box)
- Two independent but linkable apps: laptop (Python brain + Next.js orb HUD) and
  phone (Termux Python mini-brain + web orb + Capacitor APK).
- Real agent loop: perceive → decide → act → verify, with re-check after each action.
- App launch via `am start` + known-app map (HyperOS/Android 14 safe).
- Self-correction: if a UI element isn't found, it launches the app then re-finds.
- Live agent-step streaming to the HUD (orb "thinks" visibly, not just final reply).
- WebSocket links proven end-to-end: HUD↔core (laptop) and web HUD↔agent (phone).
- **Mesh**: phone pairs + relays a goal to the laptop brain; handshake deadlock fixed.
- Full model choice: any local Ollama model, or any cloud/custom OpenAI-style endpoint,
  with automatic cloud fallback when Ollama is down.
- Offline STT (Vosk, auto Hindi+English) + TTS (Piper on phone, browser on laptop).
- Screen perception: screenshot + OCR (mode B) and UiAutomator dump (mode C).
- 31 automated tests (unit + e2e + mesh + WS) passing.
- Build-ready Capacitor `android/` project committed; one-command Windows build script.
- Docs: README, CONTRIBUTING, SECURITY, this ROADMAP, LICENSE.

## 🟡 Code-complete — verify on your real gear
- Webcam hand gestures (MediaPipe) — laptop HUD + phone orb APK.
- Real Vosk mic STT and Piper TTS voices.
- Real Poco X6 Pro ADB self-control (wireless, no root).
- Premium orb shaders rendering on a real GPU.
- APK actually compiled + installed (needs an x86-64 machine; see README → Build APK).

## ⬜ Planned / ideas
- Smarter multi-turn planner with dependency graph between steps.
- Wake-word offline trigger (currently the TALK button / hold gesture).
- Cross-device "continue on the other screen" hand-off.
- Encrypted mesh pairing persisted across reboots.
- Plugin system for new tools without touching the core loop.
- iOS orb (Capacitor cross-platform — currently Android only).

## How to help
See CONTRIBUTING.md. Small, focused PRs win. Bug reports with a `selftest_phone.py`
dump are gold.
