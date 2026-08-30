"""Pluggable LLM provider layer.

Supports local Ollama AND major cloud providers through ONE OpenAI-compatible
interface. Offline-first: Ollama is default; cloud is an opt-in fallback
(config use_cloud_fallback). All providers below speak the OpenAI chat
completions shape, so swapping is just base_url + key + model.

Verified base URLs (researched):
- Ollama:        http://127.0.0.1:11434        (native /api/chat)
- OpenRouter:    https://openrouter.ai/api/v1   (OpenAI-compatible)
- TokenRouter:   https://api.tokenrouter.com/v1 (OpenAI-compatible)
- xKiro:         https://api.xkiro.com/v1       (OpenAI-compatible, key header x-api-key)
- OpenCode:      http://localhost:PORT          (OpenAI-compatible local server; user-supplied)
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional

# Provider presets: base url + auth header style
PROVIDERS: dict[str, dict] = {
    "ollama":      {"base": "http://127.0.0.1:11434", "auth": "none",   "path": "/api/chat"},
    "openrouter":  {"base": "https://openrouter.ai/api/v1", "auth": "bearer", "path": "/chat/completions"},
    "tokenrouter": {"base": "https://api.tokenrouter.com/v1", "auth": "bearer", "path": "/chat/completions"},
    "xkiro":       {"base": "https://api.xkiro.com/v1", "auth": "x-api-key", "path": "/chat/completions"},
    "opencode":    {"base": "http://localhost:8088", "auth": "bearer", "path": "/chat/completions"},
    "openai":      {"base": "https://api.openai.com/v1", "auth": "bearer", "path": "/chat/completions"},
}


@dataclass
class ProviderConfig:
    name: str = "ollama"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: str = "qwen3.5:4b"
    # Ollama uses /api/chat (no auth); OpenAI-style uses /chat/completions
    use_ollama_native: bool = True
    timeout: int = 120

    def resolve(self) -> dict:
        p = PROVIDERS.get(self.name, PROVIDERS["ollama"])
        base = (self.base_url or p["base"]).rstrip("/")
        path = p["path"]
        return {"base": base, "path": path, "auth": p["auth"]}


class LLMProvider:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.r = cfg.resolve()

    def chat(self, messages: list[dict], temperature: float = 0.3,
             max_tokens: int = 1024) -> str:
        """Return raw assistant text. Cloud path uses OpenAI chat/completions."""
        if self.cfg.use_ollama_native:
            return self._ollama(messages, temperature)
        return self._openai(messages, temperature, max_tokens)

    def _ollama(self, messages, temperature) -> str:
        payload = {"model": self.cfg.model, "messages": messages,
                   "stream": False, "options": {"temperature": temperature}}
        return self._post(self.r["base"] + "/api/chat", payload)

    def _openai(self, messages, temperature, max_tokens) -> str:
        payload = {"model": self.cfg.model, "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens, "stream": False}
        return self._post(self.r["base"] + self.r["path"], payload)

    def _post(self, url: str, payload: dict) -> str:
        data = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        if self.r["auth"] == "bearer" and self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        elif self.r["auth"] == "x-api-key" and self.cfg.api_key:
            headers["x-api-key"] = self.cfg.api_key
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.cfg.timeout) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{self.cfg.name} HTTP {e.code}: {e.read().decode()[:300]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"{self.cfg.name} unreachable: {e.reason}")
        # normalize response shape
        if "message" in body:  # ollama
            return body["message"]["content"]
        if "choices" in body:  # openai-style
            return body["choices"][0]["message"]["content"]
        raise RuntimeError(f"unknown response: {str(body)[:200]}")

    def health(self) -> bool:
        try:
            if self.cfg.use_ollama_native:
                with urllib.request.urlopen(self.r["base"] + "/api/tags", timeout=5):
                    return True
            # openai-style: hit /models
            url = self.r["base"] + "/models"
            headers = {}
            if self.r["auth"] == "bearer" and self.cfg.api_key:
                headers["Authorization"] = f"Bearer {self.cfg.api_key}"
            elif self.r["auth"] == "x-api-key" and self.cfg.api_key:
                headers["x-api-key"] = self.cfg.api_key
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=5):
                return True
        except (urllib.error.URLError, OSError):
            return False
        return False


def build_provider(name: str, model: str, api_key: Optional[str] = None,
                   base_url: Optional[str] = None) -> LLMProvider:
    """Factory. name in PROVIDERS; 'ollama' is local/offline."""
    use_native = (name == "ollama")
    return LLMProvider(ProviderConfig(name=name, base_url=base_url,
                                      api_key=api_key, model=model,
                                      use_ollama_native=use_native))
