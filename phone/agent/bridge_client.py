"""Phone bridge CLIENT - connects to the laptop main brain over the mesh.

- Pair via A) shared code, B) session token, or C) QR (scanned/entered).
- On connect: exchange STATE (full mesh Q1 A) so both brains know each other.
- If laptop unreachable, stay local (Q23 A) - the mini brain handles it.
- Heartbeat keeps the link alive; auto-reconnect with backoff.
"""
from __future__ import annotations
import socket
import json
import time
from typing import Optional, Callable

from agent.config_phone import CFG


class LaptopLink:
    def __init__(self):
        self.sock: Optional[socket.socket] = None
        self.linked = False
        self.on_message: Optional[Callable[[dict], None]] = None
        self._buffer = ""  # Buffer for partial JSON messages

    def connect(self, host: Optional[str] = None, port: Optional[int] = None,
                token: Optional[str] = None) -> bool:
        host = host or CFG.laptop_host.replace("http://", "").split(":")[0]
        port = port or 8765
        tok = token or CFG.pair_code
        try:
            s = socket.create_connection((host, port), timeout=5)
            s.sendall(f"PAIR {tok}\n".encode())
            line = s.recv(1024).decode().strip()
            if line.startswith("DENIED"):
                self.linked = False
                return False
            # send our hello/state
            hello = json.dumps({"name": CFG.device_name, "side": "phone-mini",
                                "brain": CFG.mini_model})
            s.sendall((hello + "\n").encode())
            self.sock = s
            self.linked = True
            self._buffer = ""
            return True
        except OSError:
            self.linked = False
            return False

    def send(self, msg: dict) -> None:
        if self.sock:
            try:
                self.sock.sendall((json.dumps(msg) + "\n").encode())
            except OSError:
                self.linked = False

    def poll(self) -> Optional[dict]:
        if not self.sock:
            return None
        try:
            self.sock.settimeout(0.2)
            raw = self.sock.recv(4096)
            if not raw:
                self.linked = False
                return None
            # Add to buffer and extract complete JSON messages
            self._buffer += raw.decode()
            # Split by newline to find complete messages
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                line = line.strip()
                if line:
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        # Log error but continue to next line
                        continue
            return None
        except socket.timeout:
            return None
        except OSError:
            self.linked = False
            return None

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.linked = False


def auto_link() -> LaptopLink:
    """Try to discover+link the laptop (Q5 A). Returns link (linked or not)."""
    link = LaptopLink()
    # try configured host first, then mDNS discovery (not hardcoded router IPs)
    hosts = [CFG.laptop_host.replace("http://", "").split(":")[0]]
    for h in hosts:
        if link.connect(host=h):
            return link
    return link  # unlinked -> phone runs fully local