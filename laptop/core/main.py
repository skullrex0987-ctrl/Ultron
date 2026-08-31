"""ULTRON laptop main brain - entrypoint.

Wires the HUD (WebSocket orb frontend) <-> brain (qwen3.5:4b) -> Hermes tools
-> Android control -> agent loop, and runs the mesh bridge so the phone
mini-brain can connect (full mesh, Q1 A).

Real flow:
  HUD sends {type:"talk"} -> orb goes listening -> user speaks -> browser STT
  sends {type:"transcript", text} -> Core handles it as a GOAL:
    - push state "thinking"
    - run Agent over the goal (perceive/decide/act/verify)
    - each reply -> push transcript + signal TTS (browser speaks) + audio level
    - push state "speaking" while TTS plays, then "idle"
"""
from __future__ import annotations
import asyncio
import json
import threading
from typing import Optional

try:
    import websockets  # type: ignore
    _HAVE_WS = True
except Exception:  # pragma: no cover
    _HAVE_WS = False

from config import CFG
from audit import log, transcript
from ollama_client import BrainClient
from agent import Agent, KillSwitch
from bridge import Bridge, start_bridge_in_thread, get_local_ip


class Core:
    def __init__(self):
        self.llm = BrainClient(model=CFG.main_model)
        self.agent = Agent("main", on_reply=self._on_reply, on_step=self._on_step)
        self.bridge = Bridge()
        self.hud = None
        self.loop = None
        self.wake = True
        self.busy = False

    # ---- HUD websocket (orb frontend) ----
    async def hud_handler(self, ws):
        self.hud = ws
        await self._send_hud({"type": "state", "state": "idle"})
        try:
            async for raw in ws:
                try:
                    m = json.loads(raw)
                except Exception:
                    continue
                t = m.get("type")
                if t == "transcript":
                    # browser STT result -> treat as a spoken goal/query
                    text = (m.get("text") or "").strip()
                    if text:
                        await self._handle_goal(text)
                elif t == "goal":
                    await self._handle_goal(m.get("goal", ""))
                elif t == "wake":
                    self.wake = bool(m.get("on"))
                    log("core", {"event": "wake", "on": self.wake})
                elif t == "talk":
                    await self._send_hud({"type": "state", "state": "listening"})
        except Exception as e:  # noqa
            log("core", {"event": "hud-error", "err": str(e)})

    async def _handle_goal(self, text: str):
        if self.busy:
            return
        if not self.wake and not text.lower().startswith("ultron"):
            return
        self.busy = True
        transcript(text, who="user")
        await self._send_hud({"type": "state", "state": "thinking"})
        # run the long autonomous agent OFF the event loop (it can take seconds)
        await self.loop.run_in_executor(None, self._run_agent, text)
        self.busy = False
        await self._send_hud({"type": "state", "state": "idle"})

    def _run_agent(self, text: str):
        try:
            self.agent.set_prompt(self._prompt_steps)
            self.agent.run(text)
        except KillSwitch:
            transcript("Stopped by kill-switch.", who="ultron")
        except Exception as e:  # noqa
            log("core", {"event": "goal-error", "err": str(e)})
            transcript(f"Error: {e}", who="ultron")

    def _on_reply(self, text: str):
        # TTS is handled in the browser; core just signals it + animates the orb
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self._tts_signal(text), self.loop)

    def _on_step(self, step: int, desc: str, ok: bool):
        # live HUD progress: stream each agent step as it happens (called from
        # the agent's worker thread, so schedule sends on the event loop)
        if not self.loop:
            return
        msg = {
            "type": "transcript",
            "who": "ultron",
            "text": "> " + desc,
            "status": "thinking",
        }
        asyncio.run_coroutine_threadsafe(self._send_hud(msg), self.loop)
        asyncio.run_coroutine_threadsafe(
            self._send_hud({"type": "state", "state": "thinking"}), self.loop)

    async def _tts_signal(self, text: str):
        await self._send_hud({"type": "state", "state": "speaking"})
        await self._send_hud({"type": "tts", "text": text})
        # pulse audio level briefly so the orb "mouths" the reply
        for lvl in (0.9, 0.6, 0.3, 0.1):
            await self._send_hud({"type": "audio", "level": lvl})
            await asyncio.sleep(0.12)
        await self._send_hud({"type": "audio", "level": 0.0})

    async def _prompt_steps(self, q: str) -> str:
        # In the HUD this would pop a box; headless we log + use default cap.
        log("core", {"event": "step-prompt", "q": q})
        return str(CFG.max_step_hard_cap)

    async def _send_hud(self, m: dict):
        if self.hud:
            try:
                await self.hud.send(json.dumps(m))
            except Exception:
                pass

    def push_transcript(self, who: str, text: str):
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self._send_hud({"type": "transcript", "who": who, "text": text}),
                self.loop)

    async def serve_hud(self):
        self.loop = asyncio.get_event_loop()
        async with websockets.serve(self.hud_handler, "127.0.0.1", 8766):
            log("core", {"event": "hud-ws", "port": 8766})
            await asyncio.Future()

    def run(self):
        start_bridge_in_thread(self.bridge)
        self.bridge.on_message = self._on_mesh
        log("core", {"event": "start", "brain": CFG.main_model,
                     "qr": self.bridge.qr_payload(),
                     "ip": get_local_ip()})
        try:
            asyncio.run(self.serve_hud())
        except KeyboardInterrupt:
            log("core", {"event": "stop"})

    def _on_mesh(self, m: dict, peer_id: str):
        # full mesh: a message from the phone is relayed to the HUD transcript
        log("mesh", {"from": peer_id, "msg": m})
        kind = m.get("type")
        if kind == "transcript":
            self.push_transcript(m.get("who", "phone"), m.get("text", ""))


if __name__ == "__main__":
    Core().run()
