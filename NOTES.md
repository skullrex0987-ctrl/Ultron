# ULTRON — BUILD LOG (SKULL-SWARM autonomous build)

Built autonomously via SKULL-SWARM: RESEARCH → MAKE → TEST → FIX → REPEAT.
All steps logged. This file is the backup trail.

## FINAL VERIFIED STATE (TEST gate passed)
- ✅ Python compiles + imports: laptop/core (11 modules), phone/agent (7 modules)
- ✅ 19/19 unit tests pass (test_core.py)
- ✅ Laptop HUD `next build` compiles (Next.js 16 + TypeScript clean, static export)
- ✅ Live Ollama intent parsing works on qwen2.5:0.5b (proxy for qwen3.5): open youtube,
      weather, file write, and HINDI "मेरा फोन अनलॉक करो" all parsed to valid tool JSON
- ✅ Package: /root/outbox/ultron-laptop.zip (15KB), ultron-phone.zip (325KB), ultron-orb-apk.zip (312KB)
- ✅ GitHub: committed locally (branch master). Remote push attempted -> see BLOCKER below.
- ⚠️ Telegram send: needs Inkiiibot bot token (not present in this session's env).

## ARCHITECTURE DELIVERED
LAPTOP (Windows + RTX 5060) — main brain qwen3.5:4b
  laptop/core/   config, providers (Ollama+OpenRouter+TokenRouter+xKiro+OpenCode+OpenAI),
                 brain client, tools (shell/file/web/adb/plan/reply), audit (JSONL+transcript),
                 android_control (ADB+Accessibility), perception (scrcpy+OCR / ADB screenshot+OCR / UiAutomator),
                 agent (autonomous loop, asks step count before every task, kill-switch, hard cap),
                 bridge (pair A code / B token / C QR + mDNS)
  laptop/hud/    Next.js forked Ultron orb -> renamed U.L.T.R.O.N., PREMIUM visuals
                 (shader energy core + god-rays + 1400-pt nebula + bloom + chromatic aberration),
                 audio-reactive, webcam gestures, link panel, transcript, WebSocket to core

PHONE (Poco X6 Pro, Termux, no root) — mini brain qwen3.5:0.8b
  phone/agent/   config, ollama client, tools, android self-control (ADB loopback + UiAutomator),
                 perception (3 modes), bridge CLIENT (links to laptop, full mesh state exchange,
                 auto-fallback to local brain if laptop unreachable), stt/tts (Vosk + Piper)
  phone/web/     FastAPI small orb HUD + Brahma-style gesture classifier
  phone/orb-apk/ Standalone Android APK (Capacitor WebView): Three.js orb (MATCHING premium
                 visuals) + MediaPipe hand gestures + generated logo + app name "ULTRON Orb"
  phone/floating_widget/ Kotlin overlay: tap=open, hold=talk, wake-word (Vosk)
  phone/bootstrap.sh      one-shot Termux setup

## PROVIDERS (optional cloud fallback, offline-first)
Ollama (default) + OpenRouter (https://openrouter.ai/api/v1) + TokenRouter
(https://api.tokenrouter.com/v1) + xKiro (https://api.xkiro.com/v1, header x-api-key) +
OpenCode (local OpenAI-compatible) + OpenAI. All via one interface in laptop/core/providers.py.

## BLOCKERS (need user action)
1. GITHUB PUSH 403: fine-grained PAT (skullrex0987-ctrl) reads skullrex0987-ctrl/Ultron
   (API push:True) but `git push` returns 403 "Permission denied". The token's
   "Repository access" list lacks write Contents for that repo. FIX: re-grant the token
   write access to skullrex0987-ctrl/Ultron (or provide a token with `repo` scope). Then:
       cd /root/jarvis-ultron && git remote add origin <url> && git push -u origin master:main
   Local repo is committed and ready.
2. TELEGRAM: Inkiiibot bot token not in this session's env. Provide it (or it's in your
   stored secrets) and run: python3 /root/jarvis-ultron/send_telegram.py
   Outbox files are ready at /root/outbox.

## WHAT I COULD NOT TEST HERE (environment limits — you verify on device)
- Webcam hand gestures (no camera on build box)
- Microphone Vosk STT (no audio input)
- Real Poco X6 Pro ADB/Accessibility control (no device)
- Android APK compile (no JDK/Android SDK) — project is build-ready:
    cd phone/orb-apk && npm i && npx cap add android && bash android_res/sync_icons.sh && npx cap sync android && cd android && ./gradlew assembleDebug

## FIX CYCLES (SKULL self-heal log)
- F1: rebrand JARVIS->ULTRON swept `ROOT="/root/jarvis-ultron"` -> "/root/ultron-ultron"
      in package.py -> empty zips. FIX: reset ROOT.
- F2: Ollama intent JSON parse broke on Hindi trailing text. FIX: balanced-brace JSON
      extractor + trailing-comma strip + unit test.
- F3: agent.ask_steps ignored prompt fn. FIX: init `_prompt_fn=None`; correct branch.
- F4: destructive shell cmd ran without confirm when confirm=None. FIX: block unless confirmed.
- F5: next build "command not found" because npm install hadn't finished. FIX: ran build after install.
- F6: GitHub fine-grained PAT cannot push (403). ESCALATED: committed locally, awaiting token fix.
