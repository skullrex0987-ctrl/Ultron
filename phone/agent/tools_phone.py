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


def adb_self(cmd: str, ctrl=None) -> dict:
    """Run adb against the phone itself (loopback, no root).

    cmd is the same structured sub-command language as the laptop:
      tap X Y | swipe x1 y1 x2 y2 [ms] | text "x" | keyevent K |
      launch pkg | find "text" (tap center) | home | back | recent
    If a PhoneControl instance is passed, structured methods are used
    (more reliable than raw strings).
    """
    if ctrl is not None:
        s = cmd.strip()
        try:
            if s.startswith("tap"):
                _, x, y = s.split(); return {"ok": ctrl.tap(int(x), int(y))}
            if s.startswith("swipe"):
                p = s.split(); x1, y1, x2, y2 = map(int, p[1:5])
                ms = int(p[5]) if len(p) > 5 else 300
                return {"ok": ctrl.swipe(x1, y1, x2, y2, ms)}
            if s.startswith("text"):
                return {"ok": ctrl.type(s[len("text"):].strip().strip('"').strip("'"))}
            if s.startswith("keyevent"):
                return {"ok": ctrl._adb("shell", "input", "keyevent", s.split()[1]).returncode == 0}
            if s.startswith("launch"):
                return {"ok": ctrl.launch(s.split()[1])}
            if s.startswith("find"):
                t = s[len("find"):].strip().strip('"').strip("'")
                pos = ctrl.find(t)
                return {"ok": bool(pos), "found": t, "tapped": ctrl.tap(*pos)} if pos else {"ok": False, "reason": f"not-found:{t}"}
            if s in ("home", "back", "recent"):
                code = {"home": "3", "back": "4", "recent": "187"}[s]
                return {"ok": ctrl._adb("shell", "input", "keyevent", code).returncode == 0}
        except Exception as e:  # noqa
            return {"ok": False, "reason": f"adb-error:{e}"}
    # fallback raw
    try:
        r = subprocess.run(["adb", *cmd.split()], capture_output=True, text=True, timeout=60)
        return {"ok": r.returncode == 0, "out": r.stdout[:2000]}
    except Exception as e:  # noqa
        return {"ok": False, "reason": str(e)}


def dispatch(call: dict, ctrl=None) -> dict:
    n = call.get("tool")
    a = call.get("args", {}) or {}
    if n == "shell": return shell(a.get("cmd", ""))
    if n == "file_read": return file_read(a.get("path", ""))
    if n == "file_write": return file_write(a.get("path", ""), a.get("content", ""))
    if n == "web_fetch": return web_fetch(a.get("url", ""))
    if n == "plan": return {"ok": True, "goal": a.get("goal", ""), "steps": [s.strip() for s in a.get("goal", "").replace(";", ".").split(".") if s.strip()]}
    if n == "adb": return adb_self(a.get("cmd", ""), ctrl)
    if n == "reply": return {"ok": True, "reply": a.get("text", "")}
    return {"ok": False, "reason": f"unknown:{n}"}

