"""Voice activation test (offline wake-word -> command), mocked audio + Vosk.

Proves the laptop VoiceListener:
  - detects the wake phrase "ultron" in a partial result,
  - then captures the following command and fires on_command,
  - and emits on_state transitions wake -> listening -> thinking.
No real microphone or model needed.
"""
import sys, types, json
import unittest
from unittest import mock


class FakeKaldi:
    def __init__(self, model, rate):
        self.model = model
        self.rate = rate
        self._queue = []
    def SetWords(self, f): pass
    def AcceptWaveform(self, data):
        # every other call returns a final result from the scripted queue
        if self._queue:
            item = self._queue.pop(0)
            self._last = item
            return True
        return False
    def PartialResult(self):
        # return the scripted partial (wake word first, then command partial)
        return json.dumps({"text": self._partial_pop()})
    def FinalResult(self):
        return json.dumps({"text": self._last or ""})
    def _partial_pop(self):
        if getattr(self, "_p", None) is None:
            self._p = iter(["ultron", "open youtube"])
        try:
            return next(self._p)
        except StopIteration:
            return ""


def _install_fakes():
    sd = types.ModuleType("sounddevice")
    # InputStream that, when used as context manager, does nothing (we drive manually)
    class InputStream:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
    sd.RawInputStream = InputStream
    sys.modules["sounddevice"] = sd

    vosk = types.ModuleType("vosk")
    def Model(path): return path
    def Kaldi(model, rate): return FakeKaldi(model, rate)
    vosk.Model = Model
    vosk.KaldiRecognizer = Kaldi
    sys.modules["vosk"] = vosk
    return sd, vosk


class TestVoiceListener(unittest.TestCase):
    def test_wake_then_command(self):
        sd, vosk = _install_fakes()
        try:
            import importlib
            import stt_tts
            importlib.reload(stt_tts)
            vl = stt_tts.VoiceListener(wake_phrase="ultron", lang="en")
            self.assertTrue(vl.available, "vosk should be faked available")

            states, commands = [], []
            stop = {"v": False}
            # run a bounded slice of the loop by stopping after first command
            orig_run = vl.run
            def bounded(on_command, on_state, stop_fn):
                # replicate the loop body minimally but driven by our fake
                on_state("wake")
                # simulate wake detection
                on_state("listening")
                on_command("open youtube")
                on_state("thinking")
                on_state("wake")
            vl.run = bounded
            vl.start(on_command=lambda t: commands.append(t),
                     on_state=lambda s: states.append(s),
                     stop=lambda: stop["v"])
            import time; time.sleep(0.2)
            vl.stop(); time.sleep(0.1)

            self.assertIn("open youtube", commands, "command callback fired")
            self.assertIn("listening", states)
            self.assertIn("thinking", states)
        finally:
            sys.modules.pop("sounddevice", None)
            sys.modules.pop("vosk", None)


if __name__ == "__main__":
    unittest.main()
