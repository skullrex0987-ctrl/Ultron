"""Audit log + on-screen transcript feed (Q22 A).

Uses HMAC-SHA256 for tamper-evidence. The secret key is loaded from
ULTRON_AUDIT_KEY env var. If not set, a random key is generated and stored
in a separate file (not in the log itself).
"""
from __future__ import annotations
import json
import time
import threading
import hashlib
import hmac
import os
from typing import Any

from config import CFG

_subs: list = []
_lock = threading.Lock()

# HMAC key management
_audit_key: bytes = None


def _get_audit_key() -> bytes:
    """Get or generate the HMAC key for audit log integrity."""
    global _audit_key
    if _audit_key is not None:
        return _audit_key
    
    # Try to load from env var first
    key_str = os.getenv("ULTRON_AUDIT_KEY")
    if key_str:
        _audit_key = key_str.encode("utf-8")
        return _audit_key
    
    # Try to load from key file
    key_file = os.path.join(os.path.dirname(CFG.audit_log), ".audit_key")
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            _audit_key = f.read()
        return _audit_key
    
    # Generate a new key
    _audit_key = os.urandom(32)
    os.makedirs(os.path.dirname(key_file), exist_ok=True)
    with open(key_file, "wb") as f:
        f.write(_audit_key)
    # Set restrictive permissions (owner read/write only)
    try:
        os.chmod(key_file, 0o600)
    except Exception:
        pass
    return _audit_key


def log(event: str, data: Any = None, side: str = "laptop") -> None:
    entry = {"ts": time.time(), "side": side, "event": event, "data": data}
    line = json.dumps(entry, default=str, sort_keys=True)
    # HMAC-SHA256 for tamper-evidence
    key = _get_audit_key()
    mac = hmac.new(key, line.encode(), hashlib.sha256).hexdigest()
    entry["_hmac"] = mac
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
    """Verify the HMAC emitted by log() for one parsed JSONL entry."""
    expected = entry.get("_hmac")
    if not isinstance(expected, str):
        return False
    unsigned = {k: v for k, v in entry.items() if k != "_hmac"}
    key = _get_audit_key()
    actual = hmac.new(
        key,
        json.dumps(unsigned, default=str, sort_keys=True).encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, actual)


def transcript(text: str, who: str = "ultron") -> None:
    log("transcript", {"who": who, "text": text})