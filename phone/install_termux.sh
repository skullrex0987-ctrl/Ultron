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

step 3/7 "Python deps (live pip progress; vosk via Android aar)"
# NOTE: no 'pip install --upgrade pip' here — it downloads a whole new pip
# before doing anything useful (the #1 cause of 'stuck at websockets').
# REQUIRED: agent core — abort-worthy if missing. pip runs UNsilenced so the
# user sees the live download bar; a watchdog pings every 15s so it never
# looks frozen while pip is quietly resolving.
pipws() {
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

# ---- VOSK: no Termux wheel exists (PyPI ships glibc wheels only; Termux is
# Bionic). Proven community method: install the pure-Python part from PyPI,
# then replace libvosk.so with the Bionic-built one from the OFFICIAL
# Android build (com.alphacephei:vosk-android aar on Maven Central).
install_vosk() {
  # 1) pure-Python wrapper: use the linux_aarch64 wheel with --platform so
  # pip accepts it (it only carries python code; the .so gets replaced next)
  VOSK_WHEEL="https://files.pythonhosted.org/packages/source/v/vosk/vosk-0.3.45.tar.gz"
  # prefer the universal sdist (pure python + setup.py)
  if ! pip install --no-cache-dir --timeout 120 vosk 2>/dev/null; then
    # newer pip refuses sdist? try explicit version pin
    pip install --no-cache-dir --timeout 120 "vosk==0.3.45" 2>/dev/null || return 1
  fi
  # 2) locate the installed vosk package dir
  VOSK_DIR="$(python - <<'PY'
import vosk, os
print(os.path.dirname(vosk.__file__))
PY
)" 2>/dev/null || return 1
  [ -n "$VOSK_DIR" ] && [ -d "$VOSK_DIR" ] || return 1
  # 3) fetch official Android aar and extract the Bionic libvosk.so (arm64)
  echo "   fetching official Android libvosk.so (arm64, ~12MB)…"
  AAR_URL="https://repo1.maven.org/maven2/com/alphacephei/vosk-android/0.3.47/vosk-android-0.3.47.aar"
  TMPD="$(mktemp -d)"
  curl -fsSL --retry 2 -o "$TMPD/vosk.aar" "$AAR_URL" || { rm -rf "$TMPD"; return 1; }
  unzip -p "$TMPD/vosk.aar" jni/arm64-v8a/libvosk.so > "$TMPD/libvosk.so" 2>/dev/null || { rm -rf "$TMPD"; return 1; }
  [ -s "$TMPD/libvosk.so" ] || { rm -rf "$TMPD"; return 1; }
  # 4) swap it in
  cp "$TMPD/libvosk.so" "$VOSK_DIR/libvosk.so" || { rm -rf "$TMPD"; return 1; }
  rm -rf "$TMPD"
  # 5) verify import works
  python -c "import vosk; vosk.Model" >/dev/null 2>&1 || return 1
  return 0
}

echo "   installing vosk (Android-native method)…"
( while sleep 20; do echo "   …vosk install in progress [$(date +%H:%M:%S)]"; done ) &
WD=$!
if python -c "import vosk" >/dev/null 2>&1; then kill $WD 2>/dev/null; ok "vosk (already present)"
elif install_vosk; then kill $WD 2>/dev/null; ok "vosk (Android aar method)"
else
  kill $WD 2>/dev/null
  echo "   vosk unavailable -> voice input OFF; text command box still fully works"
fi

# ---- REST: required for full functionality ----
for p in fastapi uvicorn piper-tts; do
  if python -c "import $p" >/dev/null 2>&1; then ok "$p (already present)"; continue; fi
  echo "   installing $p…"
  ( while sleep 15; do echo "   …$p still downloading [$(date +%H:%M:%S)]"; done ) &
  WD=$!
  if pip install --no-cache-dir --timeout 120 --retries 3 "$p" >/dev/null 2>&1; then kill $WD 2>/dev/null; ok "$p"
  else kill $WD 2>/dev/null; echo "   WARNING: $p failed — retry next run, feature degrades"; fi
done

# sounddevice (mic capture) — needs portaudio
if python -c "import sounddevice" >/dev/null 2>&1; then ok "sounddevice (already present)"
else
  pkg install -y portaudio >/dev/null 2>&1 || true
  ( while sleep 15; do echo "   …sounddevice still downloading [$(date +%H:%M:%S)]"; done ) &
  WD=$!
  if pip install --no-cache-dir --timeout 120 --retries 3 sounddevice >/dev/null 2>&1; then kill $WD 2>/dev/null; ok "sounddevice"
  else kill $WD 2>/dev/null; echo "   WARNING: sounddevice failed — voice input needs it"; fi
fi

python - <<'PY' 2>/dev/null || true
try:
    import vosk  # noqa
    print("   voice: vosk OK — wake word + speech enabled")
except Exception:
    print("   NOTE: vosk unavailable -> VOICE INPUT OFF.")
    print("   The agent + orb still work fully: TYPE commands in the orb's")
    print("   text box (bottom-left).")
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