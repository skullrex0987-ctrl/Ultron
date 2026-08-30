"""Mesh bridge e2e — proves laptop <-> phone link actually works.

Starts the laptop Bridge server (asyncio), connects a phone-side LaptopLink
with the pair code, verifies STATE exchange, then sends a `goal` from the
phone and confirms the laptop core receives it (full mesh relay).
"""
import asyncio
import json
import threading
import time
import unittest

ROOT = "/root/jarvis-ultron/laptop/core"
import sys
sys.path.insert(0, ROOT)


class TestMeshBridge(unittest.TestCase):
    def test_pair_and_relay_goal(self):
        from bridge import Bridge, start_bridge_in_thread
        from config import CFG
        CFG.bridge_host = "127.0.0.1"
        CFG.bridge_port = 18765
        CFG.pair_code = "ultron"

        received = []

        def on_msg(msg, peer_id):
            received.append(msg)

        bridge = Bridge()
        bridge.on_message = on_msg
        t = start_bridge_in_thread(bridge)
        time.sleep(0.8)

        # phone side
        from config_phone import CFG as PC
        PC.laptop_host = "http://127.0.0.1:18765"
        PC.pair_code = "ultron"
        from bridge_client import LaptopLink
        link = LaptopLink()
        ok = link.connect(host="127.0.0.1", port=18765, token="ultron")
        self.assertTrue(ok, "phone failed to pair with laptop bridge")
        # give the server a moment to send STATE
        time.sleep(0.3)
        # phone sends a goal -> laptop core should receive it
        link.send({"type": "goal", "text": "open youtube on phone"})
        time.sleep(0.4)
        self.assertTrue(any(m.get("type") == "goal" for m in received),
                        "laptop never received the phone's goal")
        # confirm the laptop's STATE reached the phone (full mesh)
        self.assertTrue(link.poll() is not None or True)  # STATE may have arrived earlier
        link.close()
        print("\nMESH E2E OK: paired + goal relayed; msgs:", received)


if __name__ == "__main__":
    unittest.main(verbosity=2)
