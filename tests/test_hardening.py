import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "laptop", "core"))


class TestHardening(unittest.TestCase):
    def test_audit_entry_verifies(self):
        import audit
        entry = {"ts": 1.0, "side": "test", "event": "x", "data": {"a": 1}}
        import hashlib
        unsigned = json.dumps(entry, default=str, sort_keys=True).encode()
        entry["_sha256"] = hashlib.sha256(unsigned).hexdigest()
        self.assertTrue(audit.verify_entry(entry))
        entry["data"]["a"] = 2
        self.assertFalse(audit.verify_entry(entry))

    def test_laptop_dispatch_rejects_unknown_args(self):
        from tools import dispatch
        self.assertEqual(
            dispatch({"tool": "reply", "args": {"unexpected": 1}})["reason"],
            "schema",
        )

    def test_phone_parser_accepts_surrounding_prose(self):
        sys.path.insert(0, os.path.join(ROOT, "phone", "agent"))
        from ollama_phone import _parse_json
        self.assertEqual(
            _parse_json('Answer: {"tool":"reply","args":{"text":"ok"}} later')["tool"],
            "reply",
        )

    def test_phone_status_is_safe_when_linked(self):
        sys.path.insert(0, os.path.join(ROOT, "phone", "agent"))
        import main_phone
        with mock.patch.object(main_phone.PhoneAgent, "__init__", lambda self: None):
            agent = main_phone.PhoneAgent()
        agent.linked = True
        agent.link = types.SimpleNamespace()
        agent.local = types.SimpleNamespace()
        agent.android = types.SimpleNamespace()
        agent.tts = types.SimpleNamespace()
        agent.voice = types.SimpleNamespace()
        agent.kill_file = ""
        agent.max_steps = 1
        result = agent.status()
        self.assertTrue(result["linked"])
        self.assertTrue(result["laptop"]["linked"])

    def test_phone_watchdog_passes_label_to_callback(self):
        sys.path.insert(0, os.path.join(ROOT, "phone", "agent"))
        from selfheal import HealthWatch
        seen = []
        watch = HealthWatch(on_state=lambda *args: seen.append(args))
        watch.add("ollama", lambda: False)
        watch._tick()
        self.assertEqual(seen[0], ("ollama", "recovering", "ollama down"))


if __name__ == "__main__":
    unittest.main()
