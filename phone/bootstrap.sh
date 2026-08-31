#!/usr/bin/env bash
# ULTRON phone bootstrap — run ONCE on the Poco X6 Pro in Termux.
# Installs everything needed to run the mini-brain + orb HUD + floating widget:
#   - Python deps (websockets, fastapi, uvicorn, vosk, pillow)
#   - Ollama + the qwen3.5:0.8b mini brain
#   - Vosk models (Hin+Eng) for offline STT
#   - android-tools (adb) for wireless self-control (no root)
#   - links the agent + web HUD
# After this: `python phone/agent/main_phone.py`
set -euo pipefail
echo "[ULTRON] phone bootstrap starting..."

echo "[1/7] Termux packages"
pkg update -y
pkg install -y python rust git curl wget android-tools

echo "[2/7] Python deps"
pip install --upgrade pip
pip install websockets fastapi uvicorn vosk pillow numpy

echo "[3/7] Ollama"
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
# start ollama in background
nohup ollama serve >/tmp/ollama_serve.log 2>&1 &
sleep 4
echo "[4/7] pull mini brain qwen3.5:0.8b (offline local)"
ollama pull qwen3.5:0.8b

echo "[5/7] Vosk models (Hin+Eng)"
MODELS_DIR="$HOME/models"
mkdir -p "$MODELS_DIR"
dl_vosk() {
  local name="$1" local="$2"
  if [ -d "$MODELS_DIR/$local" ]; then echo "   $local present"; return; fi
  echo "   downloading $name ..."
  cd "$MODELS_DIR"
  curl -fsSL "https://alphacephei.com/vosk/models/$name.tar.gz" -o "$name.tar.gz"
  tar xzf "$name.tar.gz" && mv "$name" "$local"
  rm -f "$name.tar.gz"
  cd "$HOME"
}
dl_vosk "vosk-model-small-hi-0.22" "vosk-hi"
dl_vosk "vosk-model-small-en-us-0.15" "vosk-en"

echo "[6/7] Piper (offline TTS)"
if ! command -v piper >/dev/null 2>&1; then
  pip install piper-tts || echo "   piper pip failed; install via pkg if needed"
fi

echo "[7/7] enable wireless debugging helper (no root)"
echo "   On the phone: Settings > Developer options > Wireless debugging > enable."
echo "   Then: adb pair <ip:port>  (copy code) ; adb connect <ip:port>"
echo "   For self-control loopback: adb tcpip 5555 && adb connect 127.0.0.1:5555"

echo "[ULTRON] bootstrap done. Quick self-test:"
echo "   cd $(pwd)/phone/agent && python selftest_phone.py"
echo "   cd $(pwd)/phone/agent && python main_phone.py"
