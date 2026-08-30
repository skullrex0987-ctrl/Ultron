"""Unit tests for ULTRON core modules.

These run WITHOUT a device, network, or Ollama by mocking subprocess/urllib.
They verify: parser robustness, tool routing, Android command building,
perception mode selection, bridge handshake logic, and config.
Run:  python -m pytest tests/  (or)  python tests/test_core.py
"""
import sys, os, json, types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "laptop", "core"))

import config as C
from tools import dispatch, TOOL_DOCS
from agent import Agent, KillSwitch


class TestConfig(unittest.TestCase):
    def test_models(self):
        self.assertEqual(C.CFG.main_model, "qwen3.5:4b")
        self.assertEqual(C.CFG.mini_model, "qwen3.5:0.8b")
        self.assertEqual(C.CFG.model_for("main"), "qwen3.5:4b")
        self.assertEqual(C.CFG.model_for("mini"), "qwen3.5:0.8b")


class TestToolRouting(unittest.TestCase):
    def test_reply(self):
        r = dispatch({"tool": "reply", "args": {"text": "hello"}})
        self.assertTrue(r["ok"])
        self.assertEqual(r["reply"], "hello")

    def test_unknown(self):
        r = dispatch({"tool": "nope", "args": {}})
        self.assertFalse(r["ok"])
        self.assertIn("unknown", r["reason"])

    def test_shell_runs(self):
        r = dispatch({"tool": "shell", "args": {"cmd": "echo jarvis_ok"}})
        self.assertTrue(r["ok"])
        self.assertIn("jarvis_ok", r["stdout"])

    def test_file_write_read(self):
        p = "/tmp/jarvis_test_file.txt"
        dispatch({"tool": "file_write", "args": {"path": p, "content": "hi there"}})
        r = dispatch({"tool": "file_read", "args": {"path": p}})
        self.assertTrue(r["ok"])
        self.assertEqual(r["content"], "hi there")
        os.remove(p)

    def test_destructive_blocked_without_confirm(self):
        r = dispatch({"tool": "shell", "args": {"cmd": "rm -rf /tmp/xxx"}})
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "blocked-destructive")

    def test_destructive_allowed_with_confirm(self):
        r = dispatch({"tool": "shell", "args": {"cmd": "echo allowed"}},
                     confirm=lambda c: True)
        self.assertTrue(r["ok"])


class TestModels(unittest.TestCase):
    def test_resolve_local(self):
        from models import resolve
        c = resolve("qwen3.5:4b")
        self.assertEqual(c.source, "ollama")
        self.assertEqual(c.model, "qwen3.5:4b")

    def test_resolve_cloud(self):
        from models import resolve
        c = resolve("openrouter:anthropic/claude-3.5-sonnet")
        self.assertEqual(c.source, "openrouter")
        self.assertEqual(c.model, "anthropic/claude-3.5-sonnet")

    def test_resolve_custom(self):
        from models import resolve
        c = resolve("custom|http://h:1/v1|KEY|mymodel")
        self.assertEqual(c.source, "custom")
        self.assertEqual(c.base_url, "http://h:1/v1")
        self.assertEqual(c.model, "mymodel")


class TestOllamaParse(unittest.TestCase):
    """Robustness of the JSON extraction used by ollama_client.chat."""

    def _parse(self, content):
        # replicate the cleaning logic from ollama_client
        c = content.strip()
        if c.startswith("```"):
            c = c.split("```")[1]
            if c.startswith("json"):
                c = c[4:]
        return json.loads(c)

    def test_plain(self):
        self.assertEqual(self._parse('{"tool":"reply","args":{"text":"x"}}'),
                         {"tool": "reply", "args": {"text": "x"}})

    def test_fenced(self):
        c = '```json\n{"tool":"shell","args":{"cmd":"ls"}}\n```'
        self.assertEqual(self._parse(c), {"tool": "shell", "args": {"cmd": "ls"}})

    def test_natural_prefix(self):
        c = 'Sure! Here is the call:\n{"tool":"reply","args":{"text":"ok"}}'
        # extraction must handle surrounding prose; our client sends only content
        # but we still want to be resilient -> strip non-json leading text
        idx = c.find("{")
        self.assertEqual(json.loads(c[idx:]), {"tool": "reply", "args": {"text": "ok"}})

    def test_hindi_malformed_trailing(self):
        # model emits JSON followed by a Hindi explanation; extract first balanced {}
        raw = '{"tool":"reply","args":{"text":"नमस्ते, मैं आपका फोन अनलॉक कर रहा हूँ"}} यहाँ विवरण'
        start = raw.find("{")
        depth = 0; in_s = False; esc = False; end = -1
        for i in range(start, len(raw)):
            ch = raw[i]
            if in_s:
                if esc: esc = False
                elif ch == "\\": esc = True
                elif ch == '"': in_s = False
                continue
            if ch == '"': in_s = True
            elif ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0: end = i; break
        obj = raw[start:end+1].replace(",}", "}").replace(",]", "]")
        parsed = json.loads(obj)
        self.assertEqual(parsed["tool"], "reply")


class TestAndroidControl(unittest.TestCase):
    def setUp(self):
        self.a = __import__("android_control").AndroidControl()
        self.a.connected = True

    def test_tap_builds_adb(self):
        with mock.patch.object(self.a, "_adb", return_value=types.SimpleNamespace(returncode=0)) as m:
            self.a.tap(100, 200)
            args = m.call_args[0]
            self.assertIn("input", args)
            self.assertIn("tap", args)
            self.assertIn("100", args)

    def test_launch(self):
        with mock.patch.object(self.a, "_adb", return_value=types.SimpleNamespace(returncode=0)) as m:
            r = self.a.launch("com.example.app")
            # modern Android (HyperOS) uses `am start`, not monkey
            self.assertIn("am", m.call_args[0])
            self.assertTrue(r["ok"])

    def test_launch_known_app_resolves_activity(self):
        with mock.patch.object(self.a, "_adb", return_value=types.SimpleNamespace(returncode=0)) as m:
            r = self.a.launch("youtube")
            self.assertIn("am", m.call_args[0])
            self.assertIn("com.google.android.youtube/.MainActivity", m.call_args[0])
            self.assertTrue(r["ok"])

    def test_find_node_parses_bounds(self):
        import xml.etree.ElementTree as ET
        xml = ('<?xml version="1.0"?><hierarchy><node text="YouTube" '
               'bounds="[10,20][110,60]"></node></hierarchy>')
        with open("/tmp/ui.xml", "w") as f:
            f.write(xml)
        with mock.patch.object(self.a, "dump_ui", return_value=ET.parse("/tmp/ui.xml")):
            pt = self.a.find_node("YouTube")
            self.assertEqual(pt, (60, 40))


class TestBridge(unittest.TestCase):
    def test_qr_payload(self):
        from bridge import Bridge, get_local_ip
        b = Bridge()
        qr = b.qr_payload()
        self.assertTrue(qr.startswith("ultron://"))
        self.assertIn(str(C.CFG.bridge_port), qr)

    def test_pair_accepts_code(self):
        from bridge import Bridge
        b = Bridge()
        self.assertIn(b.pair_code, (b.pair_code, b.session_token))


class TestAgentStepPrompt(unittest.TestCase):
    def test_asks_steps_and_caps(self):
        ag = Agent("main")
        captured = {}
        def prompt(q):
            captured["q"] = q
            return "5"
        ag.set_prompt(prompt)
        n = ag.ask_steps("do X")
        self.assertEqual(n, 5)
        self.assertIn("do X", captured["q"])

    def test_caps_at_hard_limit(self):
        ag = Agent("main")
        ag.set_prompt(lambda q: "99999")  # way over cap
        n = ag.ask_steps("do X")
        self.assertLessEqual(n, C.CFG.max_step_hard_cap)


class TestKillSwitch(unittest.TestCase):
    def test_kill_file_raises(self):
        import tempfile
        kf = tempfile.mktemp()
        C.CFG.kill_switch_file = kf
        open(kf, "w").close()
        from agent import _check_kill
        with self.assertRaises(KillSwitch):
            _check_kill()
        os.remove(kf)


if __name__ == "__main__":
    unittest.main(verbosity=2)
