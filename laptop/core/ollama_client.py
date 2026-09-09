"""Ollama/local brain client - now backed by the pluggable provider layer with
multi-provider fallback chain.

Keeps the same chat()/intent-parsing API the rest of ULTRON expects, but the
actual model call goes through providers.LLMProvider chain, so Ollama AND
OpenRouter / TokenRouter / xKiro / OpenCode / OpenAI / Anthropic all work
through one code path with automatic failover.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Optional, List

from config import CFG
from providers import build_provider, LLMProvider, build_provider_chain

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
- research: research a question on the web, returns an answer plus source URLs. args: {"query": "..."}
- adb: control the linked Android phone. args: {"cmd": "tap X Y | swipe x1 y1 x2 y2 | text \\\"...\\\" | launch pkg | keyevent KEY"}
- plan: break a goal into steps. args: {"goal": "..."}
- reply: speak to the user. args: {"text": "..."}
RULES:
- If the request is about the PHONE (open app, tap, swipe, type, unlock, search on phone), use the `adb` tool.
- If it is a general question, use `reply` (answer briefly).
- If the question needs facts you don't reliably know (what is / who is / research / find out / latest / news / price / current), use `research` first, then `reply` summarizing and ending with a "Sources:" list of the URLs.
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
    def __init__(self, provider: Optional[LLMProvider] = None, model: Optional[str] = None,
                 cloud: bool = None):
        self.model = model or CFG.main_model
        # Build provider chain (cloud-first, ollama fallback)
        self.providers: List[LLMProvider] = build_provider_chain(CFG, self.model)
        self._current_provider_idx = 0
        self.history: list[ChatMessage] = [ChatMessage("system", SYSTEM_PROMPT)]
        self._using_cloud = False
        self._provider_name = "unknown"

    @property
    def provider(self) -> LLMProvider:
        return self.providers[self._current_provider_idx] if self.providers else None

    def chat(self, user_text: str, max_steps: int = 15) -> dict:
        self.history.append(ChatMessage("user", user_text))
        msgs = [{"role": m.role, "content": m.content} for m in self.history]
        
        # Try each provider in chain until one succeeds
        last_error = None
        for i, prov in enumerate(self.providers):
            self._current_provider_idx = i
            try:
                raw = prov.chat(msgs)
                self._using_cloud = (prov.cfg.name != "ollama")
                self._provider_name = prov.cfg.name
                break
            except Exception as e:
                last_error = e
                continue
        else:
            # All providers failed
            raise RuntimeError(f"All providers failed. Last error: {last_error}")
        
        parsed = _clean(raw)
        # Store parsed content (tool call) instead of raw JSON output
        self.history.append(ChatMessage("assistant", json.dumps(parsed)))
        # Truncate history: keep system + last 10 user/assistant pairs (max 21 messages)
        if len(self.history) > 21:
            self.history = [self.history[0]] + self.history[-20:]
        return parsed

    def health(self) -> bool:
        for prov in self.providers:
            if prov.health():
                return True
        return False

    @property
    def active_provider(self) -> str:
        if self._current_provider_idx < len(self.providers):
            return self.providers[self._current_provider_idx].cfg.name
        return "unknown"

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
    print("active provider:", c.active_provider)
    print("model ready:", c.ensure_model())
    if c.health():
        print("intent test:", c.chat("open youtube on my phone and search for cats"))
