"""No-root Android device control via ADB wireless + Accessibility (Q4 A+C).

ADB handles input (tap/swipe/type/keyevent). The accessibility / UiAutomator
path gives a structured node tree (perception mode C) for robust automation.
No root required. Target = the linked phone (Poco X6 Pro).
"""
from __future__ import annotations
import subprocess
import xml.etree.ElementTree as ET
from typing import Optional

from config import CFG
from audit import log


class AndroidControl:
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        self.host = host or CFG.adb_host
        self.port = port or CFG.adb_port
        self.connected = False

    def _adb(self, *args: str) -> subprocess.CompletedProcess:
        cmd = ["adb", "-s", f"{self.host}:{self.port}", *args]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    def connect(self) -> bool:
        r = subprocess.run(["adb", "connect", f"{self.host}:{self.port}"],
                           capture_output=True, text=True, timeout=30)
        self.connected = "connected" in r.stdout or "already" in r.stdout
        log("adb", {"action": "connect", "out": r.stdout.strip()})
        return self.connected

    def tap(self, x: int, y: int) -> dict:
        r = self._adb("shell", "input", "tap", str(x), str(y))
        log("adb", {"action": "tap", "x": x, "y": y})
        return {"ok": r.returncode == 0}

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> dict:
        r = self._adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(ms))
        log("adb", {"action": "swipe", "from": [x1, y1], "to": [x2, y2]})
        return {"ok": r.returncode == 0}

    def type_text(self, text: str) -> dict:
        # use apostrophe-safe input; replace problematic chars
        safe = text.replace("'", "")
        r = self._adb("shell", "input", "text", safe)
        log("adb", {"action": "type", "len": len(text)})
        return {"ok": r.returncode == 0}

    def keyevent(self, code: str) -> dict:
        r = self._adb("shell", "input", "keyevent", code)
        return {"ok": r.returncode == 0}

    def launch(self, pkg: str, activity: str = "") -> dict:
        cmd = f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1"
        r = self._adb("shell", *cmd.split())
        log("adb", {"action": "launch", "pkg": pkg})
        return {"ok": r.returncode == 0}

    def screen_size(self) -> tuple[int, int]:
        r = self._adb("shell", "wm", "size")
        # output: Physical size: 1080x2400
        try:
            s = r.stdout.split(":")[-1].strip().split("x")
            return int(s[0]), int(s[1])
        except Exception:
            return (1080, 2400)

    def dump_ui(self) -> Optional[ET.Element]:
        """Mode C: UiAutomator node tree (accessibility). Robust, no OCR."""
        r = self._adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
        if r.returncode != 0:
            return None
        self._adb("pull", "/sdcard/ui.xml", "/tmp/ui.xml")
        try:
            return ET.parse("/tmp/ui.xml").getroot()
        except Exception:
            return None

    def find_node(self, text: str) -> Optional[tuple[int, int]]:
        """Find a tappable center point by visible text via UiAutomator."""
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
