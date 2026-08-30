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
        parsed = json.loads(content)
        self.hist.append(Msg("assistant", content))
        return parsed

    def health(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=5):
                return True
        except (urllib.error.URLError, OSError):
            return False
