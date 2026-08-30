"""End-to-end integration test for the autonomous agent loop.

Uses a FAKE Android device + FAKE LLM so we can prove the perceive->decide->
act->verify cycle actually completes a phone task WITHOUT real hardware.

Scenario: "open youtube" on a screen that has a YouTube button.
Fake LLM returns: find "YouTube"  ->  tap (from find)  ->  reply "opened".
We assert the agent (1) called find, (2) located+tapped the element, (3) finished.
"""
import os, sys, types
import unittest
from unittest import mock

ROOT = "/root/jarvis-ultron/laptop/core"
sys.path.insert(0, ROOT)


# ---- Fake Android device ----
class FakeAndroid:
    def __init__(self):
        self.calls = []
        self.connected = False
        self._ui = (
            '<?xml version="1.0"?><hierarchy>'
            '<node text="Settings" bounds="[0,0][100,50]"></node>'
            '<node text="YouTube" bounds="[200,400][360,460]"></node>'
            '<node text="Chrome" bounds="[200,500][360,560]"></node>'
            '</hierarchy>'
        )

    def connect(self):
        self.connected = True

    def dump_ui(self):
        import xml.etree.ElementTree as ET
        return ET.fromstring(self._ui)

    def find_node(self, text):
        import xml.etree.ElementTree as ET
        root = ET.fromstring(self._ui)
        for n in root.iter("node"):
            if text.lower() in (n.get("text") or "").lower():
                b = n.get("bounds", "[0,0][0,0]")[1:-1].split("][")
                x1, y1 = map(int, b[0].split(","))
                x2, y2 = map(int, b[1].split(","))
                return ((x1 + x2) // 2, (y1 + y2) // 2)
        return None

    def reached(self, text):
        return self.find_node(text) is not None

    def tap(self, x, y):
        self.calls.append(("tap", x, y))
        return {"ok": True}

    def swipe(self, *a):
        self.calls.append(("swipe", *a)); return {"ok": True}
    def type_text(self, t):
        self.calls.append(("text", t)); return {"ok": True}
    def keyevent(self, c):
        self.calls.append(("key", c)); return {"ok": True}
    def launch(self, p):
        self.calls.append(("launch", p)); return {"ok": True}
    def _adb(self, *a):
        class R: returncode = 0
        return R()


# ---- Fake LLM that plays a script ----
SCRIPT = [
    {"tool": "adb", "args": {"cmd": 'find "YouTube"'}},
    {"tool": "reply", "args": {"text": "Opened YouTube for you."}},
]


class TestAgentE2E(unittest.TestCase):
    def test_open_youtube_flow(self):
        from agent import Agent
        fake = FakeAndroid()
        a = Agent("main", on_reply=lambda t: None)
        a.android = fake
        # patch the LLM with our scripted responder
        a.llm = types.SimpleNamespace(
            chat=lambda text: SCRIPT.pop(0) if SCRIPT else {"tool": "reply", "args": {"text": "done"}},
            history=[],
        )
        # give a high step cap but the loop should stop at 'reply'
        result = a.run("open youtube", perception_mode="C")
        # 1) find was issued
        self.assertTrue(any("find" in str(c.get("cmd", "")) for c in [step.get("res", {}) for step in result["results"]] + []) or
                        any(step.get("tool") == "adb" for step in result["results"]),
                        "adb find step missing")
        # 2) a tap actually happened on the device
        self.assertTrue(any(c[0] == "tap" for c in fake.calls), "device was never tapped")
        # 3) agent finished with a reply
        replied = any("reply" in step for step in result["results"])
        self.assertTrue(replied, "did not finish with a reply")
        # 4) the tap coordinates are the YouTube center (280,430)
        self.assertIn(("tap", 280, 430), fake.calls)
        print("\nE2E OK: find->tap(280,430)->reply, device calls:", fake.calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
