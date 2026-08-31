#!/usr/bin/env python3
"""ULTRON phone self-test — run this ON the Poco in Termux.

Checks the real on-device pieces the build box could NOT verify:
  [1] adb wireless loopback (self-control, no root)
  [2] Vosk model present (Hin+Eng) for offline STT
  [3] Piper present for offline TTS
  [4] Ollama reachable (mini brain qwen3.5:0.8b)
  [5] agent WebSocket server up on :8081
  [6] web orb HUD serving on :8080
Prints PASS/FAIL per check + a one-line verdict. Fix the FAILs, re-run.

Usage:
  cd ~/ultron/phone/agent
  python selftest_phone.py
"""
from __future__ import annotations
import os
import socket
import shutil
import subprocess
import sys
import json
import urllib.request

try:
    from config_phone import CFG
except Exception:
    # fallback defaults if config import fails
    class CFG:
        vosk_model_hi = "/data/data/com.termux/files/home/models/vosk-hi"
        vosk_model_en = "/data/data/com.termux/files/home/models/vosk-en"
        piper_bin = "piper"
        ollama_host = "http://127.0.0.1:11434"
        mini_model = "qwen3.5:0.8b"


def check(name, fn) -> bool:
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"exception: {e}"
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    s = socket.socket()
    s.settimeout(1.5)
    try:
        s.connect((host, port)); return True
    except Exception:
        return False
    finally:
        s.close()


def main():
    print("=== ULTRON phone self-test (Poco X6 Pro / Termux) ===")
    results = []

    # [1] adb loopback
    def adb_check():
        adb = shutil.which("adb")
        if not adb:
            return False, "adb binary not found (pkg install android-tools)"
        r = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=10)
        # at least one device (emulator/loopback or real) listed
        lines = [l for l in r.stdout.splitlines() if l.strip() and not l.startswith("List")]
        if len(lines) < 1:
            return False, "no adb device — run 'adb connect 127.0.0.1:5555' (wireless debug)"
        return True, f"{len(lines)} device(s)"
    results.append(check("adb wireless loopback", adb_check))

    # [2] Vosk models
    def vosk_check():
        hi = os.path.isdir(CFG.vosk_model_hi)
        en = os.path.isdir(CFG.vosk_model_en)
        if hi and en:
            return True, "hi+en present"
        missing = [n for n, p in (("hi", CFG.vosk_model_hi), ("en", CFG.vosk_model_en)) if not os.path.isdir(p)]
        return False, f"missing: {','.join(missing)} (download vosk-model-small-hi-0.22 / en-us)"
    results.append(check("Vosk Hin+Eng models", vosk_check))

    # [3] Piper
    def piper_check():
        p = shutil.which(CFG.piper_bin)
        if p:
            return True, p
        return False, "piper not found (pip install piper or pkg install piper)"
    results.append(check("Piper TTS", piper_check))

    # [4] Ollama
    def ollama_check():
        try:
            d = json.loads(urllib.request.urlopen(f"{CFG.ollama_host}/api/tags", timeout=5).read())
            names = [m["name"] for m in d.get("models", [])]
            if any(CFG.mini_model.split(":")[0] in n for n in names):
                return True, f"brain {CFG.mini_model} ready"
            return False, f"model {CFG.mini_model} not pulled (ollama pull {CFG.mini_model})"
        except Exception as e:
            return False, f"Ollama unreachable: {e} (ollama serve)"
    results.append(check("Ollama mini brain", ollama_check))

    # [5] agent WS
    results.append(check("agent WebSocket :8081", lambda: (port_open(8081), "not listening — start main_phone.py")))

    # [6] web HUD
    results.append(check("orb web HUD :8080", lambda: (port_open(8080), "not serving — start uvicorn main_phone_web:app")))

    passed = sum(results)
    total = len(results)
    print(f"\n=== {passed}/{total} checks passed ===")
    if passed == total:
        print("ULTRON phone is READY. Open the orb HUD or tap the floating widget.")
    else:
        print("Fix the FAILs above, then re-run: python selftest_phone.py")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
