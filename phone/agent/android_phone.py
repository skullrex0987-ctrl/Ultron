"""Phone self-control via ADB (localhost) + Accessibility (UiAutomator). No root.

The phone runs `adb tcpip 5555` once (manual, one-time) then connects to itself
over loopback. Accessibility node tree gives structured perception (mode C).
"""
from __future__ import annotations
import subprocess
import xml.etree.ElementTree as ET
from typing import Optional

from config_phone import CFG


class PhoneControl:
    def __init__(self):
        self.ok = False

    def ensure(self) -> bool:
        # try self-connect over loopback
        r = subprocess.run(["adb", "connect", "127.0.0.1:5555"],
                           capture_output=True, text=True, timeout=20)
        self.ok = "connected" in r.stdout or "already" in r.stdout
        return self.ok

    def _adb(self, *a):
        return subprocess.run(["adb", "-s", "127.0.0.1:5555", *a],
                              capture_output=True, text=True, timeout=60)

    def tap(self, x, y):
        return self._adb("shell", "input", "tap", str(x), str(y)).returncode == 0

    def type(self, text):
        return self._adb("shell", "input", "text", text.replace("'", "")).returncode == 0

    def launch(self, pkg):
        return self._adb("shell", "monkey", "-p", pkg, "-c",
                         "android.intent.category.LAUNCHER", "1").returncode == 0

    def dump_ui(self) -> Optional[ET.Element]:
        if not self.ensure():
            return None
        self._adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
        self._adb("pull", "/sdcard/ui.xml", "/tmp/ui.xml")
        try:
            return ET.parse("/tmp/ui.xml").getroot()
        except Exception:
            return None

    def find(self, text) -> Optional[tuple]:
        root = self.dump_ui()
        if root is None:
            return None
        for node in root.iter("node"):
            if text.lower() in (node.get("text") or "").lower():
                b = node.get("bounds", "[0,0][0,0]")[1:-1].split("][")
                x1, y1 = map(int, b[0].split(","))
                x2, y2 = map(int, b[1].split(","))
                return ((x1 + x2) // 2, (y1 + y2) // 2)
        return None
