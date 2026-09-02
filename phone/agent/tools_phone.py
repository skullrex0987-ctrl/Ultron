"""Phone Hermes-style tools (same capabilities as laptop)."""
from __future__ import annotations
import os
import re as _re
import html as _html
import subprocess
import urllib.request
import urllib.parse as _uparse
from typing import Optional

from agent.config_phone import CFG

# Commands that require an explicit confirm even in auto mode (mirrors laptop)
DESTRUCTIVE = ("rm -rf", "mkfs", "dd if=", "format", "shutdown", "reboot",
               ">: /", "chmod -R", "curl | sh", "wget | sh",
               "del /s /q", "rd /s /q", "format c:", "format C:",
               "rm -fr", "rm -r -f", "shred", "rmdir /s /q")

# ---- structured output formatting (mirror of laptop tools.format_reply) ----
_THINK_RE = _re.compile(r"<think>.*?</think>", _re.DOTALL | _re.IGNORECASE)
_TAG_RE = _re.compile(r"</?(?:think|thinking|scratchpad|system|tool_call|reasoning)>",
                      _re.IGNORECASE)
_BRACKET_RE = _re.compile(r"^\s*\[(?:system|assistant|user|internal|thinking)\]\s*:?\s*",
                          _re.IGNORECASE)
_BULLET_RE = _re.compile(r"^(\s*)([*\u2022\u2013\u2014+])\s+")
_BLANKS_RE = _re.compile(r"\n{3,}")


def format_reply(text) -> str:
    """Tidy a model reply into clean Markdown-ish output (pure string fn)."""
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
            line = _BULLET_RE.sub(r"\1- ", line).rstrip()
        else:
            line = ""
        out.append(line)
    return _BLANKS_RE.sub("\n\n", "\n".join(out)).strip()


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


def shell(cmd: str, confirm=None) -> dict:
    if any(t in cmd for t in DESTRUCTIVE):
        if not confirm or not confirm(cmd):
            return {"ok": False, "reason": "blocked-destructive"}
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


def _phone_search_url(q: str) -> str:
    return "https://html.duckduckgo.com/html/?q=" + _uparse.quote_plus(q)


def research(query: str) -> dict:
    """Phone research mode: search/fetch and return answer + source URLs."""
    q = (query or "").strip()
    if not q:
        return {"ok": False, "reason": "empty-query", "answer": "", "sources": []}
    sources: list = []
    chunks: list = []
    if q.startswith("http://") or q.startswith("https://"):
        targets = [q]
        head = f"Fetched {q}"
    else:
        url = _phone_search_url(q)
        r = web_fetch(url)
        targets = _ddg_links(r.get("content", "")) if r.get("ok") else []
        head = f"Research: {q}"
        if r.get("ok"):
            sources.append(url)
    for t in targets[:3]:
        pr = web_fetch(t)
        if pr.get("ok"):
            if t not in sources:
                sources.append(t)
            txt = _strip_html(pr.get("content", ""))
            if txt:
                chunks.append(f"From {t}:\n{txt[:800]}")
    body = "\n\n".join(chunks) if chunks else "No page content could be retrieved."
    src_block = "\n".join(f"- {s}" for s in sources) or "- (none)"
    answer = format_reply(f"{head}\n\n{body}\n\nSources:\n{src_block}")
    return {"ok": bool(sources), "answer": answer, "sources": sources, "query": q}


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
    if n == "research": return research(a.get("query", a.get("q", a.get("text", ""))))
    if n == "plan": return {"ok": True, "goal": a.get("goal", ""), "steps": [s.strip() for s in a.get("goal", "").replace(";", ".").split(".") if s.strip()]}
    if n == "adb": return adb_self(a.get("cmd", ""), ctrl)
    if n == "reply": return {"ok": True, "reply": a.get("text", "")}
    return {"ok": False, "reason": f"unknown:{n}"}

