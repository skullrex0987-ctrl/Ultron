"""Self-healing layer for ULTRON phone agent (offline-first, stdlib only).

Mirror of laptop/core/selfheal.py. Provides Supervisor (restart-on-crash with
backoff), HealthWatch (periodic checks + recovery), and dep checks. Cloud is never
used. See laptop/core/selfheal.py for the full docstring.
"""
from __future__ import annotations
import os
import time
import subprocess
import threading
from typing import Callable, Optional


def log(side: str, data: dict):
    try:
        import json
        from config_phone import CFG
        with open(CFG.audit_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"side": side, **data}) + "\n")
    except Exception:
        pass


class Supervisor:
    def __init__(self, name, target, on_state=None, max_restarts=0,
                 base_delay=1.0, max_delay=30.0):
        self.name = name
        self.target = target
        self.on_state = on_state
        self.max_restarts = max_restarts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._restarts = 0
        self._stop = False
        self._thread = None

    def _state(self, s, detail=""):
        if self.on_state:
            try:
                self.on_state(self.name, s, detail)
            except Exception:
                pass

    def _loop(self):
        delay = self.base_delay
        while not self._stop:
            try:
                self._state("ok")
                self.target()
                if not self._stop:
                    self._state("ok", "target exited")
                break
            except Exception as e:
                self._restarts += 1
                if self.max_restarts and self._restarts > self.max_restarts:
                    self._state("error", f"max restarts ({self.max_restarts}): {e}")
                    break
                self._state("recovering", f"{type(e).__name__}: {e}"[:200])
                log("selfheal", {"event": "restart", "subsystem": self.name,
                                "attempt": self._restarts, "err": str(e)[:200]})
                time.sleep(min(delay, self.max_delay))
                delay = min(delay * 2, self.max_delay)

    def start(self):
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True


def check_ollama(model, base="http://127.0.0.1:11434"):
    import urllib.request, urllib.error, json as _json
    out = {"reachable": False, "has_model": False}
    try:
        with urllib.request.urlopen(base + "/api/tags", timeout=5) as r:
            tags = _json.loads(r.read().decode()).get("models", [])
        out["reachable"] = True
        out["has_model"] = any(m.get("name") == model for m in tags)
    except (urllib.error.URLError, OSError):
        out["reachable"] = False
    return out


def pull_ollama(model, base="http://127.0.0.1:11434"):
    st = check_ollama(model, base)
    if st["has_model"]:
        return True
    if not st["reachable"]:
        return False
    try:
        subprocess.run(["ollama", "pull", model], timeout=600, check=False)
        return check_ollama(model, base)["has_model"]
    except Exception:
        return False


def ensure_vosk_model(model_dir, model_name):
    if not model_dir or not model_name:
        return False
    return os.path.isdir(os.path.join(model_dir, model_name))


class HealthWatch:
    def __init__(self, interval=15.0, on_state=None):
        self.interval = interval
        self.on_state = on_state
        self.checks = []
        self._stop = False
        self._thread = None

    def add(self, label, check, recover=None):
        self.checks.append((label, check, recover))

    def _state(self, s, detail=""):
        if self.on_state:
            try:
                self.on_state(s, detail)
            except Exception:
                pass

    def _tick(self):
        for label, check, recover in self.checks:
            try:
                ok = check()
            except Exception as e:
                ok = False
                log("selfheal", {"event": "check-error", "label": label, "err": str(e)[:160]})
            if not ok:
                self._state("recovering", f"{label} down")
                log("selfheal", {"event": "unhealthy", "label": label})
                if recover:
                    try:
                        recover()
                        log("selfheal", {"event": "recovered", "label": label})
                    except Exception as e:
                        log("selfheal", {"event": "recover-failed", "label": label, "err": str(e)[:160]})

    def _loop(self):
        while not self._stop:
            self._tick()
            time.sleep(self.interval)

    def start(self):
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
