"""Pluggable LLM provider layer.

Supports local Ollama AND major cloud providers through ONE OpenAI-compatible
interface. Online-first: Cloud providers are tried first; Ollama is fallback.
All providers below speak the OpenAI chat completions shape, so swapping is
just base_url + key + model.

Verified base URLs (researched):
- Ollama:        http://127.0.0.1:11434        (native /api/chat)
- OpenRouter:    https://openrouter.ai/api/v1   (OpenAI-compatible)
- TokenRouter:   https://api.tokenrouter.com/v1 (OpenAI-compatible)
- xKiro:         https://api.xkiro.com/v1       (OpenAI-compatible, key header x-api-key)
- OpenCode:      http://localhost:PORT          (OpenAI-compatible local server; user-supplied)
- OpenAI:        https://api.openai.com/v1      (OpenAI-native)
- Anthropic:     https://api.anthropic.com/v1   (OpenAI-compatible via proxy)
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import os


# Provider presets: base url + auth header style
PROVIDERS: dict[str, dict] = {
    "ollama":      {"base": "http://127.0.0.1:11434", "auth": "none",   "path": "/api/chat", "models_path": "/api/tags"},
    "openrouter":  {"base": "https://openrouter.ai/api/v1", "auth": "bearer", "path": "/chat/completions", "models_path": "/models"},
    "tokenrouter": {"base": "https://api.tokenrouter.com/v1", "auth": "bearer", "path": "/chat/completions", "models_path": "/models"},
    "xkiro":       {"base": "https://api.xkiro.com/v1", "auth": "x-api-key", "path": "/chat/completions", "models_path": "/models"},
    "opencode":    {"base": "http://localhost:8088", "auth": "bearer", "path": "/chat/completions", "models_path": "/models"},
    "openai":      {"base": "https://api.openai.com/v1", "auth": "bearer", "path": "/chat/completions", "models_path": "/models"},
    "anthropic":   {"base": "https://api.anthropic.com/v1", "auth": "bearer", "path": "/messages", "models_path": "/models"},
}


@dataclass
class ProviderConfig:
    name: str = "openrouter"  # Default to cloud
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: str = "anthropic/claude-3.5-sonnet"
    # Ollama uses /api/chat (no auth); OpenAI-style uses /chat/completions
    use_ollama_native: bool = True
    timeout: int = 120
    # Rate limiting
    max_requests_per_minute: int = 60
    # Custom headers
    extra_headers: Dict[str, str] = field(default_factory=dict)

    def resolve(self) -> dict:
        p = PROVIDERS.get(self.name, PROVIDERS["ollama"])
        base = (self.base_url or p["base"]).rstrip("/")
        path = p["path"]
        return {"base": base, "path": path, "auth": p["auth"], "models_path": p.get("models_path", "/models")}


class LLMProvider:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.r = cfg.resolve()
        self._request_times: List[float] = []

    def chat(self, messages: list[dict], temperature: float = 0.3,
             max_tokens: int = 1024) -> str:
        """Return raw assistant text. Cloud path uses OpenAI chat/completions."""
        # Rate limiting
        self._rate_limit()
        if self.cfg.use_ollama_native:
            return self._ollama(messages, temperature)
        return self._openai(messages, temperature, max_tokens)

    def _rate_limit(self):
        import time
        now = time.time()
        # Remove requests older than 60 seconds
        self._request_times = [t for t in self._request_times if now - t < 60]
        if len(self._request_times) >= self.cfg.max_requests_per_minute:
            # Wait until we can make a request
            sleep_time = 60 - (now - self._request_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        self._request_times.append(time.time())

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
        headers.update(self.cfg.extra_headers)
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
            if not body["choices"]:
                raise RuntimeError("empty choices array")
            return body["choices"][0]["message"]["content"]
        if "content" in body:  # anthropic
            # Anthropic returns {content: [{type: "text", text: "..."}]}
            if isinstance(body["content"], list) and body["content"]:
                return body["content"][0].get("text", "")
        raise RuntimeError(f"unknown response: {str(body)[:200]}")

    def health(self) -> bool:
        try:
            if self.cfg.use_ollama_native:
                with urllib.request.urlopen(self.r["base"] + "/api/tags", timeout=5):
                    return True
            # openai-style: hit /models
            url = self.r["base"] + self.r.get("models_path", "/models")
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

    def list_models(self) -> List[str]:
        try:
            if self.cfg.use_ollama_native:
                with urllib.request.urlopen(self.r["base"] + "/api/tags", timeout=5) as resp:
                    body = json.loads(resp.read().decode())
                return [m.get("name", "") for m in body.get("models", [])]
            url = self.r["base"] + self.r.get("models_path", "/models")
            headers = {}
            if self.r["auth"] == "bearer" and self.cfg.api_key:
                headers["Authorization"] = f"Bearer {self.cfg.api_key}"
            elif self.r["auth"] == "x-api-key" and self.cfg.api_key:
                headers["x-api-key"] = self.cfg.api_key
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=5) as resp:
                body = json.loads(resp.read().decode())
            if "data" in body:
                return [m.get("id", "") for m in body["data"]]
            return []
        except Exception:
            return []


def build_provider(name: str, model: str, api_key: Optional[str] = None,
                   base_url: Optional[str] = None) -> LLMProvider:
    """Factory. name in PROVIDERS; 'ollama' is local/offline."""
    use_native = (name == "ollama")
    return LLMProvider(ProviderConfig(name=name, base_url=base_url,
                                      api_key=api_key, model=model,
                                      use_ollama_native=use_native))


def build_provider_chain(config, model: str = None) -> List[LLMProvider]:
    """Build a chain of providers in priority order."""
    providers = []
    model = model or config.main_model
    
    # Add cloud providers from priority list
    for prov_name in config.provider_priority:
        if prov_name == "ollama":
            continue  # Add ollama last
        api_key = None
        base_url = None
        
        # Get provider-specific config
        if prov_name == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY") or config.cloud_api_key
            base_url = config.cloud_base_url
        elif prov_name == "xkiro":
            api_key = os.getenv("XKIRO_API_KEY") or config.cloud_api_key
        elif prov_name == "tokenrouter":
            api_key = os.getenv("TOKENROUTER_API_KEY") or config.cloud_api_key
        elif prov_name == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
        elif prov_name == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if api_key or prov_name == "ollama":
            try:
                p = build_provider(prov_name, model, api_key, base_url)
                providers.append(p)
            except Exception:
                pass
    
    # Always add ollama as last resort
    try:
        providers.append(build_provider("ollama", config.mini_model))
    except Exception:
        pass
    
    return providers