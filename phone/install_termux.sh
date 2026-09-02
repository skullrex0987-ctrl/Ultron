#!/usr/bin/env bash
# ULTRON phone (Termux) — ONE-SHOT installer.
# Paste this single line in Termux:
#   curl -fsSL https://raw.githubusercontent.com/skullrex0987-ctrl/Ultron/main/phone/install_termux.sh | bash
#
# What it does (idempotent — safe to re-run):
#   [1] packages: python git curl wget android-tools rust binutils
#   [2] clones/updates the Ultron repo to ~/ultron
#   [3] pip deps for the agent
#   [4] Ollama (Termux build) + mini brain qwen3.5:0.8b
#   [5] Vosk models (Hin + Eng) for offline STT
#   [6] piper-tts for offline voice
#   [7] prints EXACTLY what to do next (adb tcpip, selftest, launch)
set -euo pipefail

BOLD="\033[1m"; AMBER="\033[38;5;214m"; RED="\033[31m"; GREEN="\033[32m"; R="\033[0m"
step(){ echo -e "${AMBER}${BOLD}[$1] $2${R}"; }
ok(){   echo -e "   ${GREEN}✓ $1${R}"; }
fail(){ echo -e "   ${RED}✗ $1${R}"; }

echo -e "${AMBER}${BOLD}== U.L.T.R.O.N. — Termux installer ==${R}"

step 1/7 "Termux packages"
pkg update -y >/dev/null 2>&1 || true
pkg install -y python rust binutils git curl wget android-tools >/dev/null 2>&1 || pkg install -y python git curl wget android-tools
ok "packages"

step 2/7 "ULTRON source"
if [ -d "$HOME/ultron/.git" ]; then
  (cd "$HOME/ultron" && git pull -q origin main) && ok "updated ~/ultron" || fail "git pull — check network"
else
  git clone -q --depth 1 https://github.com/skullrex0987-ctrl/Ultron.git "$HOME/ultron" && ok "cloned to ~/ultron" || fail "clone — check network"
fi

step 3/7 "Python deps"
pip install -q --upgrade pip >/dev/null 2>&1 || true
pip install -q websockets fastapi uvicorn vosk pillow numpy >/dev/null 2>&1 \
  || pip install websockets fastapi uvicorn vosk pillow numpy
ok "websockets fastapi uvicorn vosk pillow numpy"

step 4/7 "Ollama + mini brain qwen3.5:0.8b"
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | bash && ok "ollama installed" || fail "ollama install"
fi
(command -v ollama >/dev/null 2>&1) && { nohup ollama serve >"$HOME/ollama.log" 2>&1 & sleep 3; }
if command -v ollama >/dev/null 2>&1; then
  if ollama list 2>/dev/null | grep -q "qwen3.5:0.8b"; then ok "qwen3.5:0.8b already present"
  else ollama pull qwen3.5:0.8b >/dev/null 2>&1 && ok "pulled qwen3.5:0.8b" || fail "model pull (run: ollama pull qwen3.5:0.8b)"; fi
else
  echo "   (skip — install ollama manually if you want the on-phone brain)"
fi

step 5/7 "Vosk models (Hin+Eng, offline STT)"
MODELS="$HOME/models"; mkdir -p "$MODELS"
dl(){ [ -d "$MODELS/$2" ] && { ok "$2 present"; return; }
  echo "   downloading $1 (~50MB)..."
  (cd "$MODELS" && curl -fsSL "https://alphacephei.com/vosk/models/$1.tar.gz" -o "$1.tar.gz" \
    && tar xzf "$1.tar.gz" && mv "$1" "$2" && rm -f "$1.tar.gz" && ok "$2") || fail "$2 download"; }
dl "vosk-model-small-hi-0.22" "vosk-hi"
dl "vosk-model-small-en-us-0.15" "vosk-en"

step 6/7 "Piper TTS (offline voice)"
command -v piper >/dev/null 2>&1 && ok "piper present" || { pip install -q piper-tts >/dev/null 2>&1 && ok "piper-tts (pip)" || echo "   (optional — voice replies muted if absent)"; }

step 7/7 "Done — NEXT STEPS"
cat <<'EOF'

  1. Wireless self-control (one-time, no root):
       Settings > Developer options > Wireless debugging > ON
       In Termux:  adb tcpip 5555   (via USB once)  OR use:
                   adb connect 127.0.0.1:5555
  2. Self-test (all should PASS):
       cd ~/ultron/phone/agent && python selftest_phone.py
  3. Launch the phone agent:
       cd ~/ultron/phone/agent && python main_phone.py
  4. Install the Orb app (APK):
       github.com/skullrex0987-ctrl/Ultron/releases  (v1.1.0 universal)
  5. Pair with laptop: set ULTRON_LAPTOP=http://<laptop-LAN-IP>:8765
       (laptop IP shown by D:\ULTRON\START_ULTRON.bat)

EOF
echo -e "${GREEN}Installer complete. Run the self-test next.${R}"
