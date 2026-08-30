"""ULTRON laptop main brain - entrypoint.

Wires: HUD WebSocket (audio/transcript/link) <-> Ollama (qwen3.5:4b) ->
Hermes tools -> Android control -> agent loop. Also runs the mesh bridge
so the phone mini-brain can connect (full mesh, Q1 A).

Run:  python main.py
"""
from __future__ import annotations
import asyncio
import json
import threading
import websockets  # type: ignore
from typing import Optional

from config import CFG
from audit import log, transcript
from ollama_client import BrainClient
from tools import dispatch
from agent import Agent, KillSwitch
from bridge import Bridge, start_bridge_in_thread, get_local_ip


class Core:
    def __init__(self):
        self.llm = BrainClient(model=CFG.main_model)
        self.agent = Agent("main")
        self.bridge = Bridge()
        self.hud = None  # websockets server for the frontend
        self.wake = False

    # ---- HUD websocket (orb frontend) ----
    async def hud_handler(self, ws):
        self.hud = ws
        try:
            async for raw in ws:
                try:
                    m = json.loads(raw)
                except Exception:
                    continue
                if m.get("type") == "talk":
                    await self.handle_talk()
                elif m.get("type") == "wake":
                    self.wake = bool(m.get("on"))
                    log("core", {"event": "wake", "on": self.wake})
                elif m.get("type") == "goal":
                    # autonomous task; step count asked via agent.ask_steps
                    self.agent.set_prompt(self._prompt_steps)
                    self.agent.run(m.get("goal", ""))
        except Exception as e:  # noqa
            log("core", {"event": "hud-error", "err": str(e)})

    async def _send_hud(self, m: dict):
        if self.hud:
            try:
                await self.hud.send(json.dumps(m))
            except Exception:
                pass

    def _prompt_steps(self, q: str) -> str:
        """In a real UI this pops a box; headless we log + use default."""
        log("core", {"event": "step-prompt", "q": q})
        return str(CFG.max_step_hard_cap)

    async def handle_talk(self):
        # STT is browser-side (Vosk WASM); core receives transcript via hud.
        # For headless test we simulate by reading from a queue (see main()).
        await self._send_hud({"type": "state", "state": "listening"})

    def push_transcript(self, who: str, text: str):
        asyncio.run_coroutine_threadsafe(
            self._send_hud({"type": "transcript", "who": who, "text": text}), self.loop)

    def push_audio(self, level: float):
        asyncio.run_coroutine_threadsafe(
            self._send_hud({"type": "audio", "level": level}), self.loop)

    def push_link(self, status: str):
        asyncio.run_coroutine_threadsafe(
            self._send_hud({"type": "link", "state": status}), self.loop)

    async def serve_hud(self):
        self.loop = asyncio.get_event_loop()
        async with websockets.serve(self.hud_handler, "127.0.0.1", 8766):
            log("core", {"event": "hud-ws", "port": 8766})
            await asyncio.Future()

    def run(self):
        # mesh bridge
        start_bridge_in_thread(self.bridge)
        self.bridge.on_message = lambda m, pid: log("mesh", {"from": pid, "msg": m})
        log("core", {"event": "start", "brain": CFG.main_model,
                     "qr": self.bridge.qr_payload(),
                     "ip": get_local_ip()})
        try:
            asyncio.run(self.serve_hud())
        except KeyboardInterrupt:
            log("core", {"event": "stop"})


if __name__ == "__main__":
    Core().run()
