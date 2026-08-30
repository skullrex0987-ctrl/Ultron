"""Phone Hermes-style tools (same capabilities as laptop)."""
from __future__ import annotations
import os
import subprocess
import urllib.request
from typing import Optional

from config_phone import CFG


def shell(cmd: str, confirm=None) -> dict:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120,
                           cwd=os.path.expanduser("~"))
        return {"ok": True, "rc": r.returncode, "out": r.stdout[:4000], "err": r.stderr[:2000]}
    except Exception as e:  # noqa
        return {"ok": False, "reason": str(e)}


def file_read(path: str) -> dict:
    try:
        with open(os.path.expanduser(path)) as f:
            return {"ok": True, "content": f.read()[:20000]}
    except Exception as e:  # noqa
        return {"ok": False, "reason": str(e)}


def file_write(path: str, content: str) -> dict:
    try:
        p = os.path.expanduser(path)
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "w") as f:
            f.write(content)
        return {"ok": True}
    except Exception as e:  # noqa
        return {"ok": False, "reason": str(e)}


def web_fetch(url: str) -> dict:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ultron/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"ok": True, "content": r.read(200000).decode("utf-8", "replace")[:20000]}
    except Exception as e:  # noqa
        return {"ok": False, "reason": str(e)}


def dispatch(call: dict) -> dict:
    n = call.get("tool")
    a = call.get("args", {}) or {}
    if n == "shell": return shell(a.get("cmd", ""))
    if n == "file_read": return file_read(a.get("path", ""))
    if n == "file_write": return file_write(a.get("path", ""), a.get("content", ""))
    if n == "web_fetch": return web_fetch(a.get("url", ""))
    if n == "reply": return {"ok": True, "reply": a.get("text", "")}
    return {"ok": False, "reason": f"unknown:{n}"}


# adb on-device: the phone controls ITSELF via its own adb (wireless, no root)
def adb_self(cmd: str) -> dict:
    """Run adb against localhost (phone controls itself)."""
    try:
        r = subprocess.run(["adb", *cmd.split()], capture_output=True, text=True, timeout=60)
        return {"ok": r.returncode == 0, "out": r.stdout[:2000]}
    except Exception as e:  # noqa
        return {"ok": False, "reason": str(e)}
