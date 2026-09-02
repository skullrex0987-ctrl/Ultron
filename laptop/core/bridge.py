"""Device-to-device bridge + pairing (Q14 A+B+C).

- A) shared pair code (config) for home LAN
- B) auto-generated token shown in UI, copy once
- C) mDNS advertise + QR shown on laptop, phone scans
Plus: on every connect, the two brains exchange state (full mesh Q1 A).

Uses a tiny WebSocket server (no external deps beyond `websockets` if present,
else falls back to a plain asyncio socket server).
"""
from __future__ import annotations
import asyncio
import json
import os
import socket
import uuid
from typing import Optional, Callable

from config import CFG
from audit import log


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


class Bridge:
    """WebSocket-ish bridge. Each connected peer is a dict {name, side, send}.
    On connect, peers exchange a HELLO carrying device state (full mesh)."""

    def __init__(self):
        self.peers: dict[str, dict] = {}
        self.pair_code = CFG.pair_code
        self.session_token = uuid.uuid4().hex[:8]  # mode B token
        self.on_message: Optional[Callable[[dict, str], None]] = None

    def qr_payload(self) -> str:
        # mode C: QR encodes ip:port:token for phone to scan
        return f"ultron://{get_local_ip()}:{CFG.bridge_port}:{self.session_token}"

    async def handler(self, reader, writer):
        peer_id = uuid.uuid4().hex[:12]
        try:
            # handshake: first line = PAIR <code-or-token>
            line = (await reader.readline()).decode().strip()
            _, payload = (line.split(" ", 1) + [""])[:2]
            if payload not in (self.pair_code, self.session_token):
                writer.write(b"DENIED\n")
                await writer.drain()
                return
            # ACK so the client knows pairing succeeded (avoids a handshake
            # deadlock: client was waiting for a reply before sending hello).
            writer.write(b"OK\n")
            await writer.drain()
            hello = (await reader.readline()).decode().strip()
            info = json.loads(hello)
            self.peers[peer_id] = {"name": info.get("name", "peer"),
                                  "side": info.get("side", "?"),
                                  "writer": writer}
            log("bridge", {"event": "peer-connected", "id": peer_id,
                           "name": info.get("name")})
            # full mesh: send our state to them
            await self._send(peer_id, {"type": "STATE",
                                       "name": CFG.device_name, "side": "laptop-main",
                                       "state": {"brain": CFG.main_model}})
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                try:
                    msg = json.loads(raw.decode().strip())
                except json.JSONDecodeError:
                    log("bridge", {"event": "json-decode-error", "raw": raw.decode()[:200]})
                    continue
                if self.on_message:
                    self.on_message(msg, peer_id)
        except Exception as e:  # noqa
            log("bridge", {"event": "peer-error", "err": str(e)})
        finally:
            self.peers.pop(peer_id, None)

    async def _send(self, peer_id: str, msg: dict) -> None:
        w = self.peers[peer_id]["writer"]
        w.write((json.dumps(msg) + "\n").encode())
        await w.drain()

    async def broadcast(self, msg: dict) -> None:
        for pid in list(self.peers):
            try:
                await self._send(pid, msg)
            except Exception:
                pass

    async def serve(self):
        server = await asyncio.start_server(self.handler,
                                            CFG.bridge_host, CFG.bridge_port)
        log("bridge", {"event": "listening", "port": CFG.bridge_port,
                      "qr": self.qr_payload(), "token": self.session_token})
        async with server:
            await server.serve_forever()


def start_bridge_in_thread(bridge: "Bridge"):
    import threading
    loop = asyncio.new_event_loop()

    def run():
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bridge.serve())
        except RuntimeError:
            pass
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t