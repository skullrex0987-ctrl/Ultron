"""Tests for the STT/TTS wrapper logic (offline, no real Vosk model needed).

We stub the `vosk` package so we exercise the routing + JSON parsing that the
real Vosk uses, without downloading multi-hundred-MB models.
"""
import sys
import types
import unittest
from unittest import mock


# ---- fake vosk package ----
class _FakeKaldi:
    def __init__(self, model, rate):
        self._model = model
    def AcceptWaveform(self, chunk):
        # only the "en" recognizer returns a final result on first chunk
        if getattr(self._model, "lang", "en") == "en":
            self._result = '{"text": "open youtube"}'
            return True
        self._result = '{"text": ""}'
        return True
    def Result(self):
        return getattr(self, "_result", '{"text": ""}')
    def FinalResult(self):
        return '{"text": ""}'


class _FakeModel:
    def __init__(self, path):
        # encode the language folder name so the recognizer can branch
        self.lang = "hi" if "hi" in path else "en"


class _FakeVosk(types.ModuleType):
    Model = _FakeModel
    KaldiRecognizer = _FakeKaldi


sys.modules.setdefault("vosk", _FakeVosk("vosk"))


class TestVoskSTT(unittest.TestCase):
    def test_transcribe_wav_parses_en(self):
        from stt_tts import VoskSTT
        stt = VoskSTT(lang="en")
        self.assertTrue(stt.available)
        # patch _model_path so it does not hit disk
        stt._model_path = lambda lang: f"/models/{lang}"
        # create a tiny valid wav in memory via wave + BytesIO
        import io, wave
        buf = io.BytesIO()
        wf = wave.open(buf, "wb")
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 4000)
        wf.close()
        buf.seek(0)
        # wave can't open BytesIO path; write temp file instead
        import tempfile, os
        fd, p = tempfile.mkstemp(suffix=".wav"); os.close(fd)
        with open(p, "wb") as f:
            f.write(buf.getvalue())
        try:
            # monkeypatch wave.open to read our temp file
            text = stt.transcribe_wav(p, lang="en")
            self.assertIn("open youtube", text)
        finally:
            os.remove(p)

    def test_unavailable_graceful(self):
        import importlib
        # simulate vosk missing
        saved = sys.modules.get("vosk")
        sys.modules["vosk"] = None  # import fails
        try:
            from stt_tts import VoskSTT as V
            stt = V()
            self.assertFalse(stt.available)
        finally:
            sys.modules["vosk"] = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)
