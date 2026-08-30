"""Phone (Termux) agent config - mini brain qwen3.5:0.8b.

Designed to run on the Poco X6 Pro via Termux, no root. Connects to the
laptop main brain when on LAN; falls back to its own 0.8b model when the
laptop is unreachable (Q23 A).
"""
from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass
class PhoneConfig:
    ollama_host: str = os.getenv("JARVIS_OLLAMA", "http://127.0.0.1:11434")
    mini_model: str = os.getenv("JARVIS_MINI_MODEL", "qwen3.5:0.8b")
    laptop_host: str = os.getenv("JARVIS_LAPTOP", "http://192.168.1.1:8765")
    pair_code: str = os.getenv("JARVIS_PAIR_CODE", "ultron")
    device_name: str = "poco-x6pro"
    use_accessibility: bool = True
    stt_lang: str = "hi"  # Vosk Hin+Eng; switch per input
    vosk_model_hi: str = os.getenv("VOSK_HI", "/data/data/com.termux/files/home/models/vosk-hi")
    vosk_model_en: str = os.getenv("VOSK_EN", "/data/data/com.termux/files/home/models/vosk-en")
    piper_bin: str = os.getenv("PIPER", "piper")
    piper_model: str = os.getenv("PIPER_MODEL", "en_US-lessac-medium.onnx")
    auto_execute: bool = True
    require_step_prompt: bool = True
    audit_log: str = os.getenv("JARVIS_AUDIT", "/data/data/com.termux/files/home/ultron/audit.jsonl")


CFG = PhoneConfig()
