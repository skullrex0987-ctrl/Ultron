"""Self-healing layer for ULTRON (offline-first, no external deps).

Gives every long-running subsystem three recovery abilities:

1. SUPERVISION  - `Supervisor.run(target, ...)` runs `target()` and, if it raises,
   restarts it with exponential backoff (capped). Reports state to a callback so
   the HUD orb can show 'recovering' instead of silently dying.

2. HEALTH WATCHDOG - `HealthWatch` periodically pings registered checks (Ollama
   reachable, mic present, Vosk model present). On failure it tries a recovery
   action (restart subsystem, fall back to a smaller model) and notifies.

3. DEPENDENCY CHECK - `ensure_deps()` verifies the Vosk model + Ollama model exist
   at startup; if Ollama's model is missing it attempts `ollama pull` (offline-safe:
   only if Ollama itself is reachable).

All failures are logged; nothing here contacts the network except the optional,
user-initiated `ollama pull`. Cloud is never used unless CFG.use_cloud_fallback.
"""
from __future__ import annotations
import os
import time
import subprocess
import threading
from typing import Callable, Optional


def log(side: str, data: dict):
    try:
        from config import CFG
        with open(CFG.audit_log, "a", encoding="utf-8") as f:
            f.write(__import__("json").dumps({"side": side, **data}) + "\n")
    except Exception:
        pass


class Supervisor:
    """Restart a long-running callable on exception, with backoff."""

    def __init__(self, name: str, target: Callable[[], None],
                 on_state: Optional[Callable[[str, str], None]] = None,
                 max_restarts: int = 0, base_delay: float = 1.0, max_delay: float = 30.0):
        self.name = name
        self.target = target
        self.on_state = on_state  # (name, "ok"|"recovering"|"error", detail)
        self.max_restarts = max_restarts  # 0 = unlimited
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._restarts = 0
        self._stop = False
        self._thread = None

    def _state(self, s: str, detail: str = ""):
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
                # target returned cleanly (server shutdown etc.) -> exit
                if not self._stop:
                    self._state("ok", "target exited")
                break
            except Exception as e:  # noqa
                self._restarts += 1
                if self.max_restarts and self._restarts > self.max_restarts:
                    self._state("error", f"max restarts ({self.max_restarts}) exceeded: {e}")
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


def check_ollama(model: str, base: str = "http://127.0.0.1:11434") -> dict:
    """Return {'reachable': bool, 'has_model': bool}."""
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


def pull_ollama(model: str, base: str = "http://127.0.0.1:11434") -> bool:
    """Best-effort offline-safe pull. Returns True if it succeeded or was already
    present. Never raises."""
    st = check_ollama(model, base)
    if st["has_model"]:
        return True
    if not st["reachable"]:
        return False  # Ollama not running -> can't pull offline
    try:
        subprocess.run(["ollama", "pull", model], timeout=600, check=False)
        return check_ollama(model, base)["has_model"]
    except Exception:
        return False


def ensure_vosk_model(model_dir: str, model_name: str) -> bool:
    """True if the Vosk model folder exists under model_dir."""
    if not model_dir or not model_name:
        return False
    p = os.path.join(model_dir, model_name)
    return os.path.isdir(p)


class HealthWatch:
    """Periodic health watchdog with recovery hooks."""

    def __init__(self, interval: float = 15.0,
                 on_state: Optional[Callable[[str, str], None]] = None):
        self.interval = interval
        self.on_state = on_state
        self.checks = []  # (label, fn->bool, recovery_fn|None)
        self._stop = False
        self._thread = None

    def add(self, label: str, check: Callable[[], bool], recover: Optional[Callable[[], None]] = None):
        self.checks.append((label, check, recover))

    def _state(self, label: str, s: str, detail: str = ""):
        if self.on_state:
            try:
                self.on_state(label, s, detail)
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
                self._state(label, "recovering", f"{label} down")
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


def self_repair_stuck(agent_state: dict, max_idle_steps: int = 5) -> bool:
    """If the agent made no tool progress for max_idle_steps, abort the task.

    `agent_state` must expose {'steps': int, 'last_progress_step': int,
    'running': bool}. Returns True if a repair (abort) was triggered.
    """
    if not agent_state.get("running"):
        return False
    idle = agent_state.get("steps", 0) - agent_state.get("last_progress_step", 0)
    if idle >= max_idle_steps:
        log("selfheal", {"event": "stuck-abort", "idle_steps": idle})
        agent_state["running"] = False
        agent_state["aborted"] = True
        return True
    return False
