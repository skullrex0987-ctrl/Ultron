"""Ollama/local brain client - now backed by the pluggable provider layer.

Keeps the same chat()/intent-parsing API the rest of ULTRON expects, but the
actual model call goes through providers.LLMProvider, so Ollama AND OpenRouter /
TokenRouter / xKiro / OpenCode / OpenAI all work through one code path.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Optional

from config import CFG
from providers import build_provider, LLMProvider

SYSTEM_PROMPT = """You are ULTRON, a local autonomous agent. You have tools.
When the user asks for an action, respond with a JSON tool call:
{"tool": "<name>", "args": {...}}
When you just need to reply, respond with:
{"tool": "reply", "args": {"text": "..."}}
Keep responses short. Available tools:
- shell: run a command. args: {"cmd": "..."}
- file_read: args: {"path": "..."}
- file_write: args: {"path": "...", "content": "..."}
- web_fetch: args: {"url": "..."}
- adb: control the linked Android phone. args: {"cmd": "tap X Y | swipe x1 y1 x2 y2 | text \"...\" | launch pkg | keyevent KEY"}
- plan: break a goal into steps. args: {"goal": "..."}
- reply: speak to the user. args: {"text": "..."}
RULES:
- If the request is about the PHONE (open app, tap, swipe, type, unlock, search on phone), use the `adb` tool.
- If it is a general question, use `reply` (answer briefly).
- For file/web tasks use the matching tool.
Always reply with valid JSON only, no markdown fences."""


@dataclass
class ChatMessage:
    role: str
    content: str


def _clean(content: str) -> dict:
    c = content.strip()
    if c.startswith("```"):
        c = c.split("```")[1]
        if c.startswith("json"):
            c = c[4:]
    # Robustly extract the FIRST balanced JSON object, tolerating prose/Hindi
    # text, trailing commas, and unescaped chars around it.
    start = c.find("{")
    if start == -1:
        raise ValueError(f"no JSON object in model output: {c[:200]}")
    depth = 0
    in_str = False
    esc = False
    end = -1
    for i in range(start, len(c)):
        ch = c[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        raise ValueError(f"unbalanced JSON in model output: {c[:200]}")
    obj = c[start:end + 1]
    # strip trailing commas before } or ]
    obj = obj.replace(",}", "}").replace(",]", "]")
    return json.loads(obj)


class BrainClient:
    def __init__(self, provider: Optional[LLMProvider] = None, model: Optional[str] = None):
        if provider is None:
            provider = build_provider("ollama", model or CFG.main_model)
        self.provider = provider
        self.model = model or CFG.main_model
        self.history: list[ChatMessage] = [ChatMessage("system", SYSTEM_PROMPT)]

    def chat(self, user_text: str, max_steps: int = 15) -> dict:
        self.history.append(ChatMessage("user", user_text))
        msgs = [{"role": m.role, "content": m.content} for m in self.history]
        raw = self.provider.chat(msgs)
        parsed = _clean(raw)
        self.history.append(ChatMessage("assistant", raw))
        return parsed

    def health(self) -> bool:
        return self.provider.health()

    def ensure_model(self) -> bool:
        # Ollama auto-pull (Q13 A)
        try:
            import urllib.request, json as _json
            tags = _json.loads(urllib.request.urlopen(
                f"{CFG.ollama_host}/api/tags", timeout=5).read())["models"]
            if any(self.model in m.get("name", "") for m in tags):
                return True
        except Exception:
            return False
        data = _json.dumps({"model": self.model, "stream": False}).encode()
        req = urllib.request.Request(f"{CFG.ollama_host}/api/pull", data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=600).read()
            return True
        except Exception:
            return False


if __name__ == "__main__":
    c = BrainClient()
    print("health:", c.health())
    print("model ready:", c.ensure_model())
    if c.health():
        print("intent test:", c.chat("open youtube on my phone and search for cats"))
