# Security Policy — ULTRON

ULTRON is **online-first by design**. It uses cloud providers (Anthropic, OpenAI,
DeepSeek, OpenRouter) by default for maximum intelligence. Local Ollama is
available as an optional offline fallback.

## What leaves your machine?
- **Prompts and tool outputs** are sent to whichever cloud provider is active
  (Anthropic, OpenAI, DeepSeek, or OpenRouter). This includes:
  - Your messages/queries to the assistant
  - Tool results (file contents, command output, web fetch results)
  - Screen/context data when perception is active
- **Nothing** is sent unless you explicitly configure a cloud provider via
  environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`,
  `OPENROUTER_API_KEY`).
- **Mesh link** between your two devices stays on your **local LAN** (mDNS discover +
  pinned pair token). It does not traverse the internet.
- The HUD orb web UI talks only to the local brain WebSocket (`ws://127.0.0.1:8766`
  on laptop, `ws://127.0.0.1:8081` on phone).

## Data protection
- No API keys are hardcoded — all credentials come from environment variables.
- OAuth tokens for Google Workspace are stored as JSON (not pickle) with
  restrictive file permissions.
- Audit log entries are signed with HMAC-SHA256 (key stored separately from logs).
- File operations are sandboxed to `ULTRON_FS_ROOT` (default: `~/ultron/workspace`).
- Web fetch has SSRF protection (blocks private/loopback/link-local addresses).

## Kill-switch (safety)
Any device running a brain watches a kill-switch file. Create it and the agent stops
immediately and refuses new goals:
- Laptop: `touch /tmp/ultron_kill`
- Phone:  `touch /tmp/ultron_kill` (or `$ULTRON_KILL_SWITCH_FILE`)
Remove the file to resume. There is also a hard step ceiling (`ULTRON_MAX_STEP_HARD_CAP`,
default 200) so the agent can never loop forever.

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
