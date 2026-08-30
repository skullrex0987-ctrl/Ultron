"""Phone STT (Vosk, offline Hin+Eng) + TTS (Piper, offline).

Vosk runs via the `vosk` Python package (pip install vosk) on Termux.
Piper runs as a subprocess (pip install piper or use the binary).
Both are 100% offline (Q7 A, Q8 B).
"""
from __future__ import annotations
import os
import subprocess
import queue
import json
from typing import Optional, Callable

from config_phone import CFG


class VoskSTT:
    def __init__(self, lang: str = "hi"):
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
        """Consume 16k mono PCM chunks; emit partial/final text. Offline."""
        if not self.available:
            on_text("[vosk-unavailable]")
            return
        model_path = CFG.vosk_model_hi if self.lang == "hi" else CFG.vosk_model_en
        model = self.Model(model_path)
        rec = self.Kaldi(model, 16000)
        while not stop():
            chunk = audio_queue.get()
            if rec.AcceptWaveform(chunk):
                data = json.loads(rec.Result())
                if data.get("text"):
                    on_text(data["text"])


class PiperTTS:
    def __init__(self):
        self.bin = CFG.piper_bin
        self.model = CFG.piper_model

    def speak(self, text: str, out_wav: str = "/tmp/jarvis_tts.wav") -> Optional[str]:
        """Synthesize offline to a wav; Termux plays it via `play`/Termux:API."""
        try:
            p = subprocess.run([self.bin, "--model", self.model, "--output_file", out_wav],
                               input=text, capture_output=True, text=True, timeout=60)
            return out_wav if p.returncode == 0 else None
        except Exception:
            return None
