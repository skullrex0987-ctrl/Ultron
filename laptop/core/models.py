"""Model selection — full choice for the user.

You can run ANY model:
  - any local Ollama model (auto-detected from `ollama list`)
  - any cloud model via OpenRouter / TokenRouter / xKiro / OpenCode / OpenAI
  - ANY custom endpoint: provide base_url + api_key + model name

This module enumerates available models and builds the right provider so the
rest of ULTRON stays agnostic.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional

from config import CFG
from providers import LLMProvider, ProviderConfig, build_provider


CLOUD_PROVIDERS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "tokenrouter": "https://api.tokenrouter.com/v1",
    "xkiro": "https://api.xkiro.com/v1",
    "opencode": "http://localhost:8088",
    "openai": "https://api.openai.com/v1",
}


@dataclass
class ModelChoice:
    """A resolved model target."""
    source: str            # "ollama" | "openrouter" | "tokenrouter" | "xkiro" | "custom"
    model: str             # model id/name
    base_url: Optional[str] = None
    api_key: Optional[str] = None

    def to_provider(self) -> LLMProvider:
        if self.source == "ollama":
            return build_provider("ollama", self.model)
        # cloud / custom
        prov = "openai" if self.source == "custom" else self.source
        return build_provider(
            prov, self.model,
            api_key=self.api_key or CFG.cloud_api_key,
            base_url=self.base_url or CFG.cloud_base_url or CLOUD_PROVIDERS.get(self.source),
        )


def list_local_models() -> list[str]:
    """Detect models available in the local Ollama instance."""
    try:
        with urllib.request.urlopen(f"{CFG.ollama_host}/api/tags", timeout=5) as r:
            data = json.loads(r.read())
        return [m.get("name", "") for m in data.get("models", [])]
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []


def list_cloud_providers() -> dict[str, str]:
    return dict(CLOUD_PROVIDERS)


def resolve(spec: str) -> ModelChoice:
    """Parse a user spec into a ModelChoice.

    Examples:
      "qwen3.5:4b"                     -> local Ollama model
      "openrouter:anthropic/claude-3.5-sonnet" -> cloud provider + model
      "xkiro:my-model"                 -> cloud provider + model
      "custom|http://host:1234/v1|KEY|my-model" -> fully custom endpoint
    """
    if spec.startswith("custom|"):
        _, rest = spec.split("|", 1)
        parts = rest.split("|")
        base, key, model = (parts + ["", "", ""])[:3]
        return ModelChoice("custom", model, base_url=base or None, api_key=key or None)
    if ":" in spec and spec.split(":", 1)[0] in CLOUD_PROVIDERS:
        prov, model = spec.split(":", 1)
        return ModelChoice(prov, model)
    # default: treat as local Ollama model name
    return ModelChoice("ollama", spec)


def choose(spec: str) -> LLMProvider:
    """One-call: turn a user string into a ready LLMProvider."""
    return resolve(spec).to_provider()
