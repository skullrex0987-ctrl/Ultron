#!/usr/bin/env bash
# ULTRON phone bootstrap — run in Termux on the Poco X6 Pro (no root).
# Installs deps, pulls the mini brain, and starts the agent + orb web HUD.
set -e
echo "== ULTRON phone bootstrap =="
pkg update -y && pkg install -y python clang ffmpeg curl git
pip install --upgrade pip
pip install ollama vosk piper fastapi uvicorn websockets
# Ollama on Termux (proot/distro recommended; fall back to official if present)
if ! command -v ollama >/dev/null 2>&1; then
  echo "Install Ollama via: pkg install ollama  (or use a proot-distro Linux)"
fi
ollama pull qwen3.5:0.8b || true
# Vosk models (Hin+Eng, offline)
mkdir -p ~/models
[ -d ~/models/vosk-hi ] || (curl -L -o /tmp/vh.zip https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip && unzip -o /tmp/vh.zip -d ~/models && mv ~/models/vosk-model-small-hi-0.22 ~/models/vosk-hi)
[ -d ~/models/vosk-en ] || (curl -L -o /tmp/ve.zip https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip && unzip -o /tmp/ve.zip -d ~/models && mv ~/models/vosk-model-small-en-us-0.15 ~/models/vosk-en)
# one-time: enable ADB over TCP for self-control (no root)
adb tcpip 5555 || true
echo "== Starting agent =="
cd "$(dirname "$0")/agent" && nohup python main_phone.py >~/jarvis_agent.log 2>&1 &
cd "$(dirname "$0")/web" && nohup python main_phone_web.py >~/jarvis_web.log 2>&1 &
echo "Orb HUD: http://localhost:8080   |   Agent log: ~/jarvis_agent.log"
