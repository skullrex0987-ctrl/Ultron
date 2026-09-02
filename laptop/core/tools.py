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
               ">: /", "chmod -R", "curl | sh", "wget | sh",
               "del /s /q", "rd /s /q", "format c:", "format C:",
               "rm -fr", "rm -r -f", "shred", "rmdir /s /q")


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


import re as _re
import html as _html
import urllib.parse as _uparse

_THINK_RE = _re.compile(r"<think>.*?</think>", _re.DOTALL | _re.IGNORECASE)
_TAG_RE = _re.compile(r"</?(?:think|thinking|scratchpad|system|tool_call|reasoning)>",
                      _re.IGNORECASE)
_BRACKET_RE = _re.compile(r"^\s*\[(?:system|assistant|user|internal|thinking)\]\s*:?\s*",
                          _re.IGNORECASE)
_BULLET_RE = _re.compile(r"^(\s*)([*\u2022\u2013\u2014+])\s+")
_BLANKS_RE = _re.compile(r"\n{3,}")


def format_reply(text) -> str:
    """Pure-string tidy-up of a model reply into clean Markdown-ish output.

    - strips model internal tags (<think>...</think>, [system], stray tags)
    - collapses 3+ newlines into a single blank line
    - normalizes bullet markers (*, •, -, +) to '- '
    - keeps '#' headings and numbered lists as emitted
    Never raises; always returns a string.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    t = _THINK_RE.sub("", text)
    t = _TAG_RE.sub("", t)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for line in t.split("\n"):
        line = _BRACKET_RE.sub("", line)
        if line.strip():
            line = _BULLET_RE.sub(r"\1- ", line)
            line = line.rstrip()
        else:
            line = ""
        out.append(line)
    t = "\n".join(out)
    t = _BLANKS_RE.sub("\n\n", t)
    return t.strip()


def _strip_html(raw: str) -> str:
    s = _re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw or "")
    s = _re.sub(r"(?s)<[^>]+>", " ", s)
    s = _html.unescape(s)
    return _re.sub(r"[ \t\u00a0]+", " ", s).strip()


def _ddg_links(html_text: str, limit: int = 4) -> list:
    urls = []
    for m in _re.finditer(r'href="(/l/\?[^"]*uddg=[^"&]+|https?://[^"]+)"', html_text or ""):
        h = _html.unescape(m.group(1))
        if "uddg=" in h:
            q = _uparse.parse_qs(_uparse.urlparse(h).query).get("uddg")
            if q:
                h = q[0]
        if not h.startswith("http"):
            continue
        if any(d in h for d in ("duckduckgo.com", "google.com/search", "bing.com")):
            continue
        if h not in urls:
            urls.append(h)
        if len(urls) >= limit:
            break
    return urls


def research(query: str) -> dict:
    """Research mode: search/fetch pages and return an answer with citations.

    stdlib only. If `query` looks like a URL it is fetched directly; otherwise
    the DuckDuckGo HTML endpoint is searched and the top results fetched.
    Returns {'ok', 'answer', 'sources': [urls]}.
    """
    log("tool", {"tool": "research", "query": query})
    q = (query or "").strip()
    if not q:
        return {"ok": False, "reason": "empty-query", "answer": "", "sources": []}

    sources: list = []
    chunks: list = []

    if q.startswith("http://") or q.startswith("https://"):
        targets = [q]
        summary_head = f"Fetched {q}"
    else:
        url = "https://html.duckduckgo.com/html/?q=" + _uparse.quote_plus(q)
        r = web_fetch(url)
        targets = _ddg_links(r.get("content", "")) if r.get("ok") else []
        summary_head = f"Research: {q}"
        if r.get("ok"):
            sources.append(url)

    for t in targets[:3]:
        pr = web_fetch(t)
        if pr.get("ok"):
            if t not in sources:
                sources.append(t)
            txt = _strip_html(pr.get("content", ""))
            if txt:
                chunks.append(f"From {t}:\n{txt[:1200]}")

    body = "\n\n".join(chunks) if chunks else "No page content could be retrieved."
    src_block = "\n".join(f"- {s}" for s in sources) or "- (none)"
    answer = f"{summary_head}\n\n{body}\n\nSources:\n{src_block}"
    return {"ok": bool(sources), "answer": format_reply(answer),
            "sources": sources, "query": q}


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
    if name == "research":
        return research(args.get("query", args.get("q", args.get("text", ""))))
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
    "research": "Research a question on the web and return an answer with a Sources list. args: {query}",
    "adb": "Control the linked Android phone. args: {cmd: 'tap X Y' | 'swipe x1 y1 x2 y2' | 'text \"hi\"' | 'keyevent KEY' | 'launch pkg' | 'find \"YouTube\"' | 'home' | 'back' | 'recent'}",
    "plan": "Break a goal into steps. args: {goal}",
    "reply": "Speak to the user. args: {text}",
}
