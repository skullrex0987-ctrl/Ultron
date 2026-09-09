"""Phone Ollama client (qwen3.5:0.8b) - same protocol as laptop, lighter model."""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional

from config_phone import CFG

SYSTEM = """You are ULTRON mini-brain on an Android phone (Termux, no root).
You have tools. Reply with JSON only:
{"tool": "shell"|"file_read"|"file_write"|"web_fetch"|"adb"|"plan"|"reply", "args": {...}}
For chat, use {"tool":"reply","args":{"text":"..."}}."""


@dataclass
class Msg:
    role: str
    content: str


def _parse_json(content: str) -> dict:
    c = (content or "").strip()
    if c.startswith("```"):
        parts = c.split("```", 2)
        c = parts[1] if len(parts) > 1 else c
        if c.lstrip().startswith("json"):
            c = c.lstrip()[4:]
    start = c.find("{")
    if start < 0:
        raise ValueError("no JSON object in model output")
    depth = 0
    in_str = False
    escaped = False
    end = -1
    for i in range(start, len(c)):
        ch = c[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        raise ValueError("unbalanced JSON in model output")
    return json.loads(c[start:end + 1].replace(",}", "}").replace(",]", "]"))


class PhoneLLM:
    def __init__(self, host: Optional[str] = None, model: Optional[str] = None):
        self.host = (host or CFG.ollama_host).rstrip("/")
        self.model = model or CFG.mini_model
        self.hist = [Msg("system", SYSTEM)]

    def chat(self, text: str) -> dict:
        self.hist.append(Msg("user", text))
        payload = {"model": self.model,
                   "messages": [{"role": m.role, "content": m.content} for m in self.hist],
                   "stream": False, "options": {"temperature": 0.3}}
        data = json.dumps(payload).encode()
        req = urllib.request.Request(f"{self.host}/api/chat", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            content = json.loads(r.read())["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        parsed = _parse_json(content)
        self.hist.append(Msg("assistant", json.dumps(parsed)))
        return parsed

    def health(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=5):
                return True
        except (urllib.error.URLError, OSError):
            return False
