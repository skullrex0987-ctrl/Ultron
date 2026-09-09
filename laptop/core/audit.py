"""Audit log + on-screen transcript feed (Q22 A)."""
from __future__ import annotations
import json
import time
import threading
import hashlib
import hmac
from typing import Any

from config import CFG

_subs: list = []
_lock = threading.Lock()


def log(event: str, data: Any = None, side: str = "laptop") -> None:
    entry = {"ts": time.time(), "side": side, "event": event, "data": data}
    line = json.dumps(entry, default=str, sort_keys=True)
    sha = hashlib.sha256(line.encode()).hexdigest()
    entry["_sha256"] = sha
    # re-serialize so the written line carries its integrity hash
    line = json.dumps(entry, default=str, sort_keys=True)
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


def verify_entry(entry: dict) -> bool:
    """Verify the hash emitted by log() for one parsed JSONL entry."""
    expected = entry.get("_sha256")
    if not isinstance(expected, str):
        return False
    unsigned = {k: v for k, v in entry.items() if k != "_sha256"}
    actual = hashlib.sha256(
        json.dumps(unsigned, default=str, sort_keys=True).encode()
    ).hexdigest()
    return hmac.compare_digest(expected, actual)


def transcript(text: str, who: str = "ultron") -> None:
    log("transcript", {"who": who, "text": text})