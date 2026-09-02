#!/usr/bin/env bash
# ULTRON phone (Termux) — ONE-SHOT installer.
# Paste this single line in Termux:
#   curl -fsSL https://raw.githubusercontent.com/skullrex0987-ctrl/Ultron/main/phone/install_termux.sh | bash
#
# What it does (idempotent — safe to re-run):
#   [1] packages: python git curl wget android-tools rust binutils
#   [2] clones/updates the Ultron repo to ~/ultron
#   [3] pip deps for the agent (vosk built from source)
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

step 3/7 "Python deps (all required packages with live progress)"
# NOTE: no 'pip install --upgrade pip' here — it downloads a whole new pip
# before doing anything useful (the #1 cause of 'stuck at websockets').
# REQUIRED: agent core — abort-worthy if missing. pip runs UNsilenced so the
# user sees the live download bar; a watchdog pings every 15s so it never
# looks frozen while pip is quietly resolving.
pipws() {
  # 15s watchdog keeps printing so a slow network never looks frozen
  ( while sleep 15; do echo "   …still working (pip resolving/downloading — slow networks take minutes) [$(date +%H:%M:%S)]"; done ) &
  local WD=$!
  pip install --no-cache-dir --timeout 120 --retries 3 websockets
  local RC=$?
  kill $WD 2>/dev/null
  return $RC
}
if python -c "import websockets" >/dev/null 2>&1; then ok "websockets (already present)"
elif pipws; then ok "websockets"
else
  echo "   pip slow/failed -> trying Termux's binary pkg (usually seconds)…"
  pkg install -y python-websockets >/dev/null 2>&1 && ok "websockets (pkg)" || {
    fail "websockets (REQUIRED — the agent cannot run without it)"; exit 1; }
fi

# BUILD VOSK FROM SOURCE (required for wake word detection)
# Since Rust/Cargo are installed in step 1, we can build vosk from source
# This handles Python versions without pre-built wheels (like Python 3.14)
step 3a "Building VOSK from source (required for wake word detection)"
echo "   Building vosk from source (this may take several minutes)..."
# Install build dependencies for vosk
pkg install -y python-dev clang make cmake >/dev/null 2>&1 || true
pipws_vosk() {
  ( while sleep 15; do echo "   …still building vosk (this takes several minutes) [$(date +%H:%M:%S)]"; done ) &
  local WD=$!
  pip install --no-cache-dir --timeout 300 --retries 3 vosk
  local RC=$?
  kill $WD 2>/dev/null
  return $RC
}
if python -c "import vosk" >/dev/null 2>&1; then ok "vosk (already present)"
elif pipws_vosk; then ok "vosk (built from source)"
else
  echo "   WARNING: vosk build failed - wake word detection will be unavailable"
  echo "   You can still use the text command box in the Orb app"
fi

# REQUIRED PACKAGES (no longer optional - install everything)
echo "   Installing required packages..."
for p in fastapi uvicorn pillow numpy piper-tts; do
  if python -c "import $p" >/dev/null 2>&1; then ok "$p (already present)"; continue; fi
  echo "   installing $p..."
  if pip install --no-cache-dir --timeout 60 --retries 2 "$p" >/dev/null 2>&1; then ok "$p"
  else echo "   WARNING: $p install failed (will retry on next run)"; fi
done

# Verify sounddevice is available for voice input
if python -c "import sounddevice" >/dev/null 2>&1; then ok "sounddevice (already present)"
else
  echo "   installing sounddevice..."
  if pip install --no-cache-dir --timeout 60 --retries 2 sounddevice >/dev/null 2>&1; then ok "sounddevice"
  else echo "   WARNING: sounddevice install failed"; fi
fi

python - <<'PY' 2>/dev/null || true
try:
    import vosk  # noqa
    print("   voice: vosk OK — wake word + speech enabled")
except Exception:
    print("   NOTE: vosk unavailable on this Python -> VOICE INPUT OFF.")
    print("   The agent + orb still work fully: TYPE commands in the orb's")
    print("   text box (bottom-left). Retry 'vosk' later once a wheel ships."
PY

step 4/7 "Ollama + mini brain qwen3.5:0.8b"
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | bash && ok "ollama installed" || fail "ollama install"
fi
(command -v ollama >/dev/null 2>&1) && { nohup ollama serve >"$HOME/ollama.log" 2>&1 & sleep 3; }
if command -v ollama >/dev/null 2>&1; then
  if ollama list 2>/dev/null | grep -q "qwen3.5:0.8b"; then ok "qwen3.5:0.8b already present"
  else ollama pull qwen3.5:0.8b >/dev/null 2>&1 && ok "pulled qwen3.5:0.8b" || fail "model pull (run: ollama pull qwen3.5:0.8b)"
fi
else
  echo "   (skip — install ollama manually if you want the on-phone brain)"
fi

step 5/7 "Vosk models (Hin+Eng, offline STT)"
MODELS="$HOME/models"; mkdir -p "$MODELS"
dl(){ [ -d "$MODELS/$2" ] && { ok "$2 present"; return; }
  echo "   downloading $1 (~50MB)..."
  local ext="tar.gz"; case "$1" in *hi*) ext="zip";; esac
  (cd "$MODELS" && curl -fsSL "https://alphacephei.com/vosk/models/$1.$ext" -o "m.$ext" \
    && { [ "$ext" = zip ] && unzip -q -o m.zip || tar xzf m.tar.gz; } \
    && rm -f m.zip m.tar.gz && mv "$1" "$2" && ok "$2") || fail "$2 download"; }
dl "vosk-model-small-hi-0.22" "vosk-hi"
dl "vosk-model-small-en-us-0.15" "vosk-en"

step 6/7 "Piper TTS (offline voice)"
command -v piper >/dev/null 2>&1 && ok "piper present" || { pip install -q piper-tts >/dev/null 2>&1 && ok "piper-tts (pip)" || echo "   (optional — voice replies muted if absent)"; }

step 7/7 "ultron command + easy launcher"
mkdir -p "$HOME/bin"
cat > "$HOME/bin/ultron" <<'ULTRON_CMD'
#!/usr/bin/env bash
# ULTRON phone control: ultron start|stop|test|update|log
U="$HOME/ultron/phone/agent"
case "$1" in
  start)  nohup python "$U/main_phone.py" > "$HOME/ultron_agent.log" 2>&1 &
          sleep 2; pgrep -f main_phone.py >/dev/null && echo "✓ ULTRON agent running (:8081)" || { echo "✗ failed — see ~/ultron_agent.log"; exit 1; } ;;
  stop)   pkill -f main_phone.py && echo "✓ stopped" || echo "(not running)" ;;
  test)   python "$U/selftest_phone.py" ;;
  update) (cd "$HOME/ultron" && git pull -q origin main) && echo "✓ updated" ;;
  log)    tail -f "$HOME/ultron_agent.log" ;;
  *)      echo "usage: ultron start|stop|test|update|log" ;;
esac
ULTRON_CMD
chmod +x "$HOME/bin/ultron"
grep -q 'export PATH="$HOME/bin:$PATH"' "$HOME/.bashrc" 2>/dev/null || \
  echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.bashrc"
export PATH="$HOME/bin:$PATH"
ok "run:  ultron start   (then ultron test / ultron log / ultron stop / ultron update)"

step 7/7 "done — DAILY USE"
cat <<'EOF'

  DAILY USE (just these):
    ultron start     # launch the agent (:8081)
    ultron test      # self-test, all should PASS
    ultron log       # live agent log
    ultron stop      # stop it
    ultron update    # update from git

  Orb app: install the ULTRON Orb APK (v1.2.4+, universal, offline)
    direct download:
      curl -fsSL -o ~/ultron-orb.apk https://github.com/skullrex0987-ctrl/Ultron/releases/latest/download/ULTRON-Orb-universal.apk
    then on the phone: open the file, allow "install unknown apps", install
    open the orb -> tap the ⚙ button -> agent URL: ws://127.0.0.1:8081
    (same phone = 127.0.0.1; gestures + voice + text commands work fully offline)

  One-time (wireless self-control, no root):
    Settings > Developer options > Wireless debugging > ON
    Termux:  adb tcpip 5555   then   ultron test

  Pair with laptop (optional):
    export ULTRON_LAPTOP=http://<laptop-LAN-IP>:8765
    (laptop IP shown by D:\ULTRON\START_ULTRON.bat)

EOF
echo -e "${GREEN}Installer complete. Run:  ultron start${R}"