# Security Policy — ULTRON

ULTRON is **offline-by-default**. No cloud, no API keys, no telemetry are required
to run the core system. Everything (wake word, STT, brain, TTS, screen perception,
device control) runs locally on your own hardware.

## What leaves your machine?
- **Nothing**, unless you explicitly opt in:
  - Cloud LLM fallback (OpenRouter / TokenRouter / xKiro / OpenCode / OpenAI) — only
    used when you set `ULTRON_CLOUD_FB=1` and provide a URL + key. Your prompts then
    go to that provider.
  - Mesh link between your two devices — stays on your **local LAN** (mDNS discover +
    pinned pair token). It does not traverse the internet.
- The HUD orb web UI talks only to the local brain WebSocket (`ws://127.0.0.1:8766`
  on laptop, `ws://127.0.0.1:8081` on phone).

## Kill-switch (safety)
Any device running a brain watches a kill-switch file. Create it and the agent stops
immediately and refuses new goals:
- Laptop: `touch /tmp/ultron_kill`
- Phone:  `touch /tmp/ultron_kill` (or `$ULTRON_KILL_SWITCH_FILE`)
Remove the file to resume. There is also a hard step ceiling (`ULTRON_MAX_STEP_HARD_CAP`,
default 8) so the agent can never loop forever.

## Permissions used
- **ADB wireless debugging** (no root) on the phone for self-control. Pair once in
  Developer Options → Wireless debugging.
- **Accessibility service** (optional, phone) for richer UI perception.
- Microphone + camera for STT / gesture vision — only when you tap TALK / grant camera.

## Reporting a vulnerability
This is a personal project. Please open a **private** security advisory on GitHub
(skullrex0987-ctrl/Ultron → Security → Advisories) or message the maintainer directly.
Do not post exploitable details in public issues.

## Supply-chain notes
- The Android APK is built from the committed Capacitor `android/` project via
  `phone/orb-apk/build-apk.ps1` (or `.sh`). Review the gradle files before building.
- `package.py` only zips local source for offline transfer — it makes no network calls.
