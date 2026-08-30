"""Laptop STT/TTS bridge.

- STT: Vosk in the browser (WASM) is the default for the HUD; this module is a
  headless fallback using the `vosk` Python package if you run core without a browser.
- TTS: browser SpeechSynthesis on the HUD side (Q8 B). For headless, this can
  shell out to `espeak`/`piper` if present.
"""
from __future__ import annotations
import os
import subprocess
import json
import queue
from typing import Optional, Callable

from config import CFG


class VoskSTT:
    def __init__(self, lang: str = "en"):
        self.lang = lang
        try:
            from vosk import Model, KaldiRecognizer  # type: ignore
            self.Model = Model
            self.Kaldi = KaldiRecognizer
            self.available = True
        except Exception:
            self.available = False

    def transcribe_stream(self, audio_queue: "queue.Queue[bytes]", on_text: Callable[[str], None],
                          stop: Callable[[], bool]):
        if not self.available:
            on_text("[vosk-unavailable]"); return
        mp = CFG.vosk_model_dir
        model = self.Model(os.path.join(mp, CFG.hin_model if self.lang == "hi" else CFG.en_model))
        rec = self.Kaldi(model, 16000)
        while not stop():
            chunk = audio_queue.get()
            if rec.AcceptWaveform(chunk):
                d = json.loads(rec.Result())
                if d.get("text"):
                    on_text(d["text"])


class BrowserTTS:
    """TTS is performed in the browser via SpeechSynthesis; core just signals level."""
    @staticmethod
    def signal_level(level: float) -> dict:
        return {"type": "audio", "level": level}
