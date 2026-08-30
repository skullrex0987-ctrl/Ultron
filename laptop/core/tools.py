"""Hermes-style tool set - everything a Hermes agent can do (Q: both devices).

Safe, sandboxed-ish local tools. shell is the powerful one; gated by a
confirm callback for destructive commands when not in full-auto mode.
"""
from __future__ import annotations
import os
import subprocess
import urllib.request
from typing import Callable, Optional

from config import CFG
from audit import log

# Commands that require an explicit confirm even in auto mode
DESTRUCTIVE = ("rm -rf", "mkfs", "dd if=", "format", "shutdown", "reboot",
               ">: /", "chmod -R", "curl | sh", "wget | sh")


def _needs_confirm(cmd: str) -> bool:
    return any(t in cmd for t in DESTRUCTIVE)


def shell(cmd: str, confirm: Optional[Callable[[str], bool]] = None) -> dict:
    if _needs_confirm(cmd):
        # destructive: block unless an explicit confirm callback approves
        if not confirm or not confirm(cmd):
            return {"ok": False, "reason": "blocked-destructive"}
    log("tool", {"tool": "shell", "cmd": cmd})
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=180, cwd=os.path.expanduser("~"))
        return {"ok": True, "returncode": r.returncode,
                "stdout": r.stdout[:8000], "stderr": r.stderr[:4000]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "timeout"}
    except Exception as e:  # noqa
        return {"ok": False, "reason": str(e)}


def file_read(path: str) -> dict:
    log("tool", {"tool": "file_read", "path": path})
    try:
        with open(os.path.expanduser(path), "r", encoding="utf-8", errors="replace") as f:
            return {"ok": True, "content": f.read()[:20000]}
    except Exception as e:  # noqa
        return {"ok": False, "reason": str(e)}


def file_write(path: str, content: str) -> dict:
    log("tool", {"tool": "file_write", "path": path, "bytes": len(content)})
    try:
        p = os.path.expanduser(path)
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return {"ok": True}
    except Exception as e:  # noqa
        return {"ok": False, "reason": str(e)}


def web_fetch(url: str) -> dict:
    log("tool", {"tool": "web_fetch", "url": url})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ultron/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read(200000).decode("utf-8", "replace")
        return {"ok": True, "content": data[:20000]}
    except Exception as e:  # noqa
        return {"ok": False, "reason": str(e)}


def plan(goal: str) -> dict:
    """Break a goal into ordered steps (used by the agent before acting)."""
    log("tool", {"tool": "plan", "goal": goal})
    steps = [s.strip() for s in goal.replace(";", ".").split(".") if s.strip()]
    return {"ok": True, "goal": goal, "steps": steps or [goal]}


def adb(android, raw: str) -> dict:
    """Execute a structured adb command on the linked phone.

    Supported sub-commands (model emits these as plain text):
      tap X Y
      swipe x1 y1 x2 y2 [ms]
      text "some text"
      keyevent KEY
      launch pkg
      find "visible text"     -> locate via UiAutomator and tap center
      home / back / recent
    Returns a normalized result dict.
    """
    if android is None:
        return {"ok": False, "reason": "no-android-connected"}
    s = raw.strip()
    log("tool", {"tool": "adb", "cmd": s})
    try:
        if s.startswith("tap"):
            _, x, y = s.split()
            return {"ok": True, **android.tap(int(x), int(y))}
        if s.startswith("swipe"):
            parts = s.split()
            x1, y1, x2, y2 = map(int, parts[1:5])
            ms = int(parts[5]) if len(parts) > 5 else 300
            return {"ok": True, **android.swipe(x1, y1, x2, y2, ms)}
        if s.startswith("text"):
            txt = s[len("text"):].strip().strip('"').strip("'")
            return {"ok": True, **android.type_text(txt)}
        if s.startswith("keyevent"):
            return {"ok": True, **android.keyevent(s.split()[1])}
        if s.startswith("launch"):
            return {"ok": True, **android.launch(s.split()[1])}
        if s.startswith("find"):
            txt = s[len("find"):].strip().strip('"').strip("'")
            pos = android.find_node(txt)
            if pos:
                return {"ok": True, "found": txt, "tapped": android.tap(*pos)}
            return {"ok": False, "reason": f"not-found:{txt}"}
        if s in ("home", "back", "recent"):
            code = {"home": "3", "back": "4", "recent": "187"}[s]
            return {"ok": True, **android.keyevent(code)}
        # fallback: raw passthrough (legacy)
        r = android._adb(*s.split())
        return {"ok": r.returncode == 0, "rc": r.returncode}
    except Exception as e:  # noqa
        return {"ok": False, "reason": f"adb-error:{e}"}


def dispatch(tool_call: dict, confirm: Optional[Callable[[str], bool]] = None,
             android=None) -> dict:
    """Route a structured tool call (from OllamaClient.chat) to the right tool."""
    name = tool_call.get("tool")
    args = tool_call.get("args", {}) or {}
    if name == "shell":
        return shell(args.get("cmd", ""), confirm)
    if name == "file_read":
        return file_read(args.get("path", ""))
    if name == "file_write":
        return file_write(args.get("path", ""), args.get("content", ""))
    if name == "web_fetch":
        return web_fetch(args.get("url", ""))
    if name == "plan":
        return plan(args.get("goal", ""))
    if name == "adb":
        return adb(android, args.get("cmd", ""))
    if name == "reply":
        return {"ok": True, "reply": args.get("text", "")}
    return {"ok": False, "reason": f"unknown-tool:{name}"}


# Map of tool name -> doc for the planner/agent
TOOL_DOCS = {
    "shell": "Run a local shell command. args: {cmd}",
    "file_read": "Read a file. args: {path}",
    "file_write": "Write a file. args: {path, content}",
    "web_fetch": "Fetch a URL. args: {url}",
    "adb": "Control the linked Android phone. args: {cmd: 'tap X Y' | 'swipe x1 y1 x2 y2' | 'text \"hi\"' | 'keyevent KEY' | 'launch pkg' | 'find \"YouTube\"' | 'home' | 'back' | 'recent'}",
    "plan": "Break a goal into steps. args: {goal}",
    "reply": "Speak to the user. args: {text}",
}
