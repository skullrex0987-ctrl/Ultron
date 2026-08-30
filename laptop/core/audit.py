"""Audit log + on-screen transcript feed (Q22 A)."""
from __future__ import annotations
import json
import time
import threading
from typing import Any

from config import CFG

_subs: list = []
_lock = threading.Lock()


def log(event: str, data: Any = None, side: str = "laptop") -> None:
    entry = {"ts": time.time(), "side": side, "event": event, "data": data}
    line = json.dumps(entry, default=str)
    try:
        with open(CFG.audit_log, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    with _lock:
        for cb in _subs:
            try:
                cb(entry)
            except Exception:
                pass


def subscribe(cb) -> None:
    with _lock:
        _subs.append(cb)


def transcript(text: str, who: str = "ultron") -> None:
    log("transcript", {"who": who, "text": text})
