"""ULTRON laptop core - configuration.

All paths/env are overridable via env vars so the same code runs on Windows
and Linux. Defaults target the dev/test environment (this build box).
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # --- LLM (main brain) ---
    ollama_host: str = field(default_factory=lambda: os.getenv("JARVIS_OLLAMA", "http://127.0.0.1:11434"))
    main_model: str = field(default_factory=lambda: os.getenv("JARVIS_MAIN_MODEL", "qwen3.5:4b"))
    test_model: str = field(default_factory=lambda: os.getenv("JARVIS_TEST_MODEL", "qwen2.5:0.5b"))  # fast CI/test model
    # even smaller option per user request (135M)
    tiny_model: str = "smollm:135m"
    mini_model: str = field(default_factory=lambda: os.getenv("JARVIS_MINI_MODEL", "qwen3.5:0.8b"))
    # When linked, laptop can remote to phone's mini brain if its own is down.
    use_cloud_fallback: bool = field(default_factory=lambda: os.getenv("JARVIS_CLOUD_FB", "0") == "1")
    cloud_base_url: Optional[str] = field(default_factory=lambda: os.getenv("JARVIS_CLOUD_URL"))
    cloud_api_key: Optional[str] = field(default_factory=lambda: os.getenv("JARVIS_CLOUD_KEY"))

    # --- STT / TTS ---
    stt_engine: str = "vosk"          # laptop STT is browser-side; this is for headless CLI use
    tts_engine: str = "browser"       # browser SpeechSynthesis on laptop; piper on phone
    vosk_model_dir: str = field(default_factory=lambda: os.getenv("JARVIS_VOSK", "/root/models/vosk"))
    hin_model: str = "vosk-model-small-hi-0.22"
    en_model: str = "vosk-model-small-en-us-0.15"

    # --- Device control (no-root phone) ---
    adb_host: str = field(default_factory=lambda: os.getenv("JARVIS_ADB_HOST", "127.0.0.1"))
    adb_port: int = field(default_factory=lambda: int(os.getenv("JARVIS_ADB_PORT", "5555")))
    use_accessibility: bool = True     # UiAutomator node-tree perception available

    # --- Link / mesh ---
    bridge_host: str = field(default_factory=lambda: os.getenv("JARVIS_BRIDGE_HOST", "0.0.0.0"))
    bridge_port: int = field(default_factory=lambda: int(os.getenv("JARVIS_BRIDGE_PORT", "8765")))
    pair_code: str = field(default_factory=lambda: os.getenv("JARVIS_PAIR_CODE", "ultron"))
    device_name: str = "laptop-main"

    # --- Safety ---
    auto_execute: bool = True          # full auto (Q17/21 C)
    require_step_prompt: bool = True   # MUST ask user for step count before autonomous task
    kill_switch_file: str = field(default_factory=lambda: os.getenv("JARVIS_KILL", "/tmp/ultron_kill"))
    max_step_hard_cap: int = 200       # absolute ceiling even if user asks for more

    # --- Logging ---
    audit_log: str = field(default_factory=lambda: os.getenv("JARVIS_AUDIT", "/root/jarvis-ultron/laptop/core/audit.jsonl"))

    # --- Network discovery ---
    mdns_service: str = "_ultron._tcp.local."

    def model_for(self, side: str) -> str:
        return self.main_model if side == "main" else self.mini_model


# Global singleton
CFG = Config()
