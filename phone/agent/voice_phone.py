"""Phone native offline wake-word voice activation (mirrors the laptop VoiceListener).

Uses Vosk partial results for an offline "ultron" wake phrase, sounddevice for
mic capture, and on_command / on_state callbacks. If sounddevice / vosk are not
importable on the phone (e.g. Termux without the packages) it degrades
gracefully by setting ``available = False`` and emitting a friendly state.

Wire it into PhoneAgent.run() so the phone listens continuously. On the wake
word the HUD receives state "listening", then the captured command is run as a
task. The existing gesture / talk / transcript handling is untouched.
"""
from __future__ import annotations
import json
from typing import Callable, Optional

from config_phone import CFG


class VoiceListener:
    """Continuous, offline voice activation for the phone (no browser needed).

    Owns the mic via sounddevice and runs a two-phase loop:
      1) WAKE    -- listen for the wake phrase ("ultron" / "hey ultron")
      2) COMMAND -- once awakened, capture the command until speech ends (VAD)
      3) callback(on_command=text) and on_state("wake" | "listening" | "thinking")

    Fully offline (Vosk partial results detect the wake word). The HUD orb
    already animates on state changes, so this drives the "voice detection"
    animation.
    """

    def __init__(self, wake_phrase: str = "ultron", lang: str = "en"):
        self.wake = wake_phrase.lower()
        self.lang = lang
        self._thread = None
        self._stop = False
        self.available = self._deps_ok()

    def _deps_ok(self) -> bool:
        try:
            import sounddevice  # noqa: F401
            from vosk import Model, KaldiRecognizer  # type: ignore
            self.Model = Model
            self.Kaldi = KaldiRecognizer
            return True
        except Exception:
            return False

    def _model_path(self, lang: str) -> str:
        # Phone config keeps full model-directory paths (not a shared base dir).
        return CFG.vosk_model_hi if lang == "hi" else CFG.vosk_model_en

    def run(self, on_command: Callable[[str], None],
            on_state: Callable[[str], None],
            stop: Callable[[], bool] = lambda: False):
        """Blocking loop. Call from a thread.

        on_state fires with: idle | wake | listening | thinking | mic-unavailable
        | vosk-unavailable | mic-error:<msg>.
        """
        try:
            import sounddevice as sd  # type: ignore
        except Exception:
            self.available = False
            on_state("mic-unavailable")
            return
        if not self.available:
            on_state("vosk-unavailable")
            return

        try:
            rec = self.Kaldi(self.Model(self._model_path(self.lang)), 16000)
        except Exception as e:
            on_state("model-error:" + str(e)[:60])
            return
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
                            # reset recognizer to drop the wake word from transcript
                            rec = self.Kaldi(self.Model(self._model_path(self.lang)), 16000)
                            rec.SetWords(False)
                    else:  # command phase: capture until a final result arrives
                        if rec.AcceptWaveform(b""):
                            final = json.loads(rec.FinalResult()).get("text", "").strip()
                            if final:
                                on_state("thinking")
                                on_command(final)
                                on_state("wake")
                                phase = "wake"
                                rec = self.Kaldi(self.Model(self._model_path(self.lang)), 16000)
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
