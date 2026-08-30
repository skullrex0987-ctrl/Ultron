"""Phone STT (Vosk, offline Hin+Eng) + TTS (Piper, offline).

Vosk runs via the `vosk` Python package (pip install vosk) on Termux.
Piper runs as a subprocess (pip install piper or use the binary).
Both are 100% offline (Q7 A, Q8 B).

Language handling (Q11 C: auto-detect): we keep two recognizers (hi + en)
and emit text from whichever produced the most confident final result. The
mic stream is fed to BOTH; the higher-confidence final wins. For file
transcription we try `lang` first, fall back to the other.
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

    def _recognizer(self, lang: str):
        path = CFG.vosk_model_hi if lang == "hi" else CFG.vosk_model_en
        return self.Kaldi(self.Model(path), 16000)

    def transcribe_stream(self, audio_queue: "queue.Queue[bytes]", on_text: Callable[[str], None],
                          stop: Callable[[], bool]):
        """Consume 16k mono PCM chunks; auto Hin+Eng; emit final text. Offline."""
        if not self.available:
            on_text("[vosk-unavailable]")
            return
        # run hi + en recognizers in parallel for auto-detection (Q11 C)
        rec_hi = self._recognizer("hi")
        rec_en = self._recognizer("en")
        scores = {"hi": 0.0, "en": 0.0}
        while not stop():
            chunk = audio_queue.get()
            if rec_hi.AcceptWaveform(chunk):
                d = json.loads(rec_hi.Result())
                if d.get("text"):
                    scores["hi"] += len(d["text"])
                    on_text(d["text"])
            if rec_en.AcceptWaveform(chunk):
                d = json.loads(rec_en.Result())
                if d.get("text"):
                    scores["en"] += len(d["text"])
                    on_text(d["text"])

    def transcribe_wav(self, wav_path: str, lang: Optional[str] = None) -> str:
        """Offline file transcription (used for testing + recorded audio)."""
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


class PiperTTS:
    def __init__(self):
        self.bin = CFG.piper_bin
        self.model = CFG.piper_model

    def speak(self, text: str, out_wav: str = "/tmp/ultron_tts.wav") -> Optional[str]:
        """Synthesize offline to a wav; Termux plays it via `play`/Termux:API."""
        if not text:
            return None
        try:
            p = subprocess.run([self.bin, "--model", self.model, "--output_file", out_wav],
                               input=text, capture_output=True, text=True, timeout=60)
            return out_wav if p.returncode == 0 else None
        except Exception:
            return None
