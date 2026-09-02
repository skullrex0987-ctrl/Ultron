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


class VoiceListener:
    """Continuous, offline voice activation for the laptop (no browser needed).

    Owns the laptop microphone directly via sounddevice, runs a two-phase loop:
      1) WAKE  — listen for the wake phrase ("ultron" / "hey ultron")
      2) COMMAND — once awakened, capture the command until speech ends (VAD)
      3) callback(on_command=text) and on_state("wake"|"listening"|"thinking")

    Fully offline (Vosk partial results detect the wake word). The HUD orb already
    animates on state changes, so this drives the "voice detection" animation.
    """

    def __init__(self, wake_phrase: str = "ultron", lang: str = "en"):
        self.wake = wake_phrase.lower()
        self.lang = lang
        self._thread = None
        self._stop = False
        self.available = self._vosk_ok()

    def _vosk_ok(self) -> bool:
        try:
            from vosk import Model, KaldiRecognizer  # type: ignore
            self.Model = Model
            self.Kaldi = KaldiRecognizer
            return True
        except Exception:
            return False

    def _model_path(self, lang: str) -> str:
        from config import CFG
        name = CFG.hin_model if lang == "hi" else CFG.en_model
        return os.path.join(CFG.vosk_model_dir, name)

    def run(self, on_command: Callable[[str], None],
                on_state: Callable[[str], None],
                stop: Callable[[], bool] = lambda: False):
            """Blocking loop. Call from a thread. on_state: 'wake'|'listening'|'thinking'."""
            import numpy as np  # type: ignore
            try:
                import sounddevice as sd  # type: ignore
            except Exception:
                on_state("mic-unavailable")
                return
            if not self.available:
                on_state("vosk-unavailable")
                return

            # Cache the Model instance (expensive disk load) - only create KaldiRecognizer when needed
            self._cached_model = self.Model(self._model_path(self.lang))
            rec = self.Kaldi(self._cached_model, 16000)
            rec.SetWords(False)
            on_state("idle")

            def cb(indata, frames, t, status):
                rec.AcceptWaveform(bytes(indata))

            try:
                with sd.RawInputStream(samplerate=16000, blocksize=8000,
                                       dtype="int16", channels=1, callback=cb):
                    phase = "wake"
                    on_state("wake")
                    while not self._stop and not stop():
                        if rec.AcceptWaveform(b""):  # force a result flush
                            pass
                        partial = rec.PartialResult()
                        text = json.loads(partial).get("text", "").lower()
                        if phase == "wake":
                            if self.wake in text or ("hey" in text and "ultron" in text):
                                on_state("listening")
                                phase = "command"
                                # reset recognizer to drop the wake word from transcript (reuse cached Model)
                                rec = self.Kaldi(self._cached_model, 16000)
                                rec.SetWords(False)
                        else:  # command phase: capture until a final result arrives
                            if rec.AcceptWaveform(b""):
                                final = json.loads(rec.FinalResult()).get("text", "").strip()
                                if final:
                                    on_state("thinking")
                                    on_command(final)
                                    on_state("wake")
                                    phase = "wake"
                                    rec = self.Kaldi(self._cached_model, 16000)
                                    rec.SetWords(False)
            except Exception as e:
                on_state("mic-error:" + str(e)[:60])

    def start(self, on_command, on_state, stop=lambda: False):
        import threading
        self._stop = False
        self._thread = threading.Thread(target=self.run, args=(on_command, on_state, stop),
                                        daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True

class VoskSTT:
    """Vosk-based offline STT (headless fallback).

    Auto Hin+Eng: feed the stream to hi + en recognizers, emit final text.
    The browser uses Web Speech; this is for running core without a browser.
    """

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
