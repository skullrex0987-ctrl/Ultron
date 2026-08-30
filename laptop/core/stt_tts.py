"""Laptop STT/TTS bridge.

- STT: Vosk in the browser (WASM) is the default for the HUD; this module is a
  headless fallback using the `vosk` Python package if you run core without a browser.
  Auto Hin+Eng: feed the stream to hi + en recognizers, emit final text (Q11 C).
- TTS: browser SpeechSynthesis on the HUD side (Q8 B). For headless, shell out
  to `piper`/`espeak` if present.
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

    def _model_path(self, lang: str) -> str:
        # CFG.vosk_model_dir is the BASE dir that already contains the unpacked
        # model folder (e.g. /root/models/vosk/vosk-model-small-hi-0.22).
        name = CFG.hin_model if lang == "hi" else CFG.en_model
        return os.path.join(CFG.vosk_model_dir, name)

    def _recognizer(self, lang: str):
        return self.Kaldi(self.Model(self._model_path(lang)), 16000)

    def transcribe_stream(self, audio_queue: "queue.Queue[bytes]", on_text: Callable[[str], None],
                          stop: Callable[[], bool]):
        if not self.available:
            on_text("[vosk-unavailable]"); return
        rec_hi = self._recognizer("hi")
        rec_en = self._recognizer("en")
        while not stop():
            chunk = audio_queue.get()
            if rec_hi.AcceptWaveform(chunk):
                d = json.loads(rec_hi.Result())
                if d.get("text"):
                    on_text(d["text"])
            if rec_en.AcceptWaveform(chunk):
                d = json.loads(rec_en.Result())
                if d.get("text"):
                    on_text(d["text"])

    def transcribe_wav(self, wav_path: str, lang: Optional[str] = None) -> str:
        if not self.available:
            return ""
        lang = lang or self.lang
        try:
            import wave
            wf = wave.open(wav_path, "rb")
            rec = self._recognizer(lang)
            out = []
            while True:
                data = wf.readframes(4000)
                if not data:
                    break
                if rec.AcceptWaveform(data):
                    out.append(json.loads(rec.Result()).get("text", ""))
            out.append(json.loads(rec.FinalResult()).get("text", ""))
            return " ".join(x for x in out if x).strip()
        except Exception:
            return ""


class BrowserTTS:
    """TTS is performed in the browser via SpeechSynthesis; core just signals level."""

    @staticmethod
    def signal_level(level: float) -> dict:
        return {"type": "audio", "level": level}
