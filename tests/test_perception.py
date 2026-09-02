"""Perception mode B (screenshot + OCR) test.

Uses a fake Android handle that returns PNG bytes, and monkeypatches _ocr_bytes
so we prove the screencap->OCR pipeline wires correctly without a real device
or tesseract.
"""
import sys
import os
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "laptop", "core"))


class TestPerception(unittest.TestCase):
    def test_mode_b_routes_through_android_and_ocr(self):
        import perception

        fake_android = types.SimpleNamespace(
            _adb=lambda *a: types.SimpleNamespace(stdout=b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)
        )
        captured = {}

        def fake_ocr(data):
            captured["data"] = data
            return "YouTube Settings"

        with mock.patch.object(perception, "_ocr_bytes", fake_ocr):
            text = perception.mode_b_adb_ocr(fake_android)
        self.assertEqual(text, "YouTube Settings")
        # the screencap bytes were passed straight to OCR
        self.assertTrue(captured["data"].startswith(b"\x89PNG"))

    def test_mode_c_returns_items(self):
        import xml.etree.ElementTree as ET
        import perception
        xml = ('<?xml version="1.0"?><hierarchy>'
               '<node text="YouTube" bounds="[0,0][100,50]"></node>'
               '<node text="Chrome" bounds="[0,60][100,110]"></node>'
               '</hierarchy>')
        fake_android = types.SimpleNamespace(dump_ui=lambda: ET.fromstring(xml))
        items = perception.mode_c_uiautomator(fake_android)
        self.assertEqual([i["text"] for i in items], ["YouTube", "Chrome"])

    def test_perceive_dispatches(self):
        import perception
        fake_android = types.SimpleNamespace(dump_ui=lambda: None)
        scene = perception.perceive(fake_android, mode="C")
        self.assertEqual(scene["mode"], "C")
        self.assertEqual(scene["items"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
