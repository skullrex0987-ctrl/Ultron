"""Phone (Termux) agent orchestrator - REAL loop + mesh WebSocket server.

- Runs qwen3.5:0.8b locally (mini brain) for full autonomy offline.
- Serves a WebSocket on :8081 so the phone web HUD (orb + gestures, port 8080)
  and the laptop mesh bridge can talk to it.
- Connects to the laptop main brain when available (full mesh Q1 A); falls back
  to local brain if laptop unreachable (Q23 A).
- Self-controls the phone via ADB loopback + UiAutomator (no root):
  perceive (3 modes) -> decide -> act -> verify, same as the laptop agent.
- Speaks replies via Piper (offline) and accepts Vosk STT (offline Hin+Eng).
"""
from __future__ import annotations
import os
import json
import socket
import threading
import time
import asyncio
from typing import Optional

try:
    import websockets  # type: ignore
    _HAVE_WS = True
except Exception:  # pragma: no cover
    _HAVE_WS = False

from config_phone import CFG
from ollama_phone import PhoneLLM
from tools_phone import dispatch, adb_self, format_reply
from android_phone import PhoneControl
from bridge_client import auto_link, LaptopLink
from stt_tts_phone import VoskSTT, PiperTTS
import selfheal
from selfheal import HealthWatch, check_ollama, pull_ollama
from voice_phone import VoiceListener


def log(side: str, data: dict):
    try:
        with open(CFG.audit_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"side": side, **data}) + "\n")
    except Exception:
        pass


class PhoneAgent:
    def __init__(self):
        self.local = PhoneLLM()
        self.android = PhoneControl()
        self.ctrl = self.android
        self.linked = False
        self.link: Optional[LaptopLink] = None
        self.tts = PiperTTS()
        self.voice = VoiceListener()
        self.kill_file = CFG.kill_switch_file
        self.max_steps = CFG.max_step_hard_cap
        self.hud_clients: set = set()
        # self-healing watchdog: monitor Ollama brain + voice availability
        self.watch = HealthWatch(interval=20.0, on_state=self._on_heal_state)
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.busy = False

    # ---- mesh (laptop) ----
    def connect_laptop(self) -> bool:
        self.link = auto_link()
        self.linked = self.link.linked
        if self.linked:
            threading.Thread(target=self._mesh_poll, daemon=True).start()
        return self.linked

    def _mesh_poll(self):
        if not self.link:
            return
        while self.linked:
            try:
                m = self.link.poll()
                if m and m.get("type") == "goal":
                    self.run_task(m.get("text", ""), self.max_steps)
            except Exception:
                self.linked = False
                break

    def chat(self, text: str) -> dict:
        """Reason with laptop brain if linked, else local 0.8b (Q23 A)."""
        if self.linked and self.link:
            self.link.send({"type": "reason", "text": text})
        return self.local.chat(text)

    # ---- WebSocket server (:8081) for web HUD + bridge ----
    async def handler(self, ws):
        self.hud_clients.add(ws)
        try:
            await ws.send(json.dumps({"type": "state", "state": "idle"}))
            await ws.send(json.dumps({"type": "transcript", "who": "ultron",
                                      "text": "ULTRON agent linked. Gestures + voice ready."}))
            async for raw in ws:
                try:
                    m = json.loads(raw)
                except Exception:
                    continue
                t = m.get("type")
                if t == "transcript":
                    text = (m.get("text") or "").strip()
                    if text:
                        await self._handle_goal(text)
                elif t == "goal":
                    await self._handle_goal(m.get("goal", ""))
                elif t == "talk":
                    await self._send_hud({"type": "state", "state": "listening"})
                elif t == "gesture":
                    self._on_gesture(m.get("action"))
        except Exception:
            pass
        finally:
            self.hud_clients.discard(ws)

    def _on_gesture(self, action):
        if action == "talk":
            self._send_hud_sync({"type": "transcript", "who": "ultron",
                                 "text": "Listening… speak now."})
            self._send_hud_sync({"type": "state", "state": "listening"})
        elif action == "screenshot":
            r = self.android._adb("shell", "screencap", "-p", "/sdcard/ultron_shot.png")
            if r.returncode == 0:
                self._send_hud_sync({"type": "transcript", "who": "ultron",
                                     "text": "Screenshot saved to /sdcard/ultron_shot.png"})
        elif action == "volup":
            self.android._adb("shell", "input", "keyevent", "24")
            self._send_hud_sync({"type": "transcript", "who": "ultron",
                                 "text": "Volume up."})
        elif action == "voldown":
            self.android._adb("shell", "input", "keyevent", "25")
            self._send_hud_sync({"type": "transcript", "who": "ultron",
                                 "text": "Volume down."})
        elif action == "listen":
            self._send_hud_sync({"type": "state", "state": "listening"})
            self._send_hud_sync({"type": "transcript", "who": "ultron",
                                 "text": "Voice capture on — say 'ultron' then a command."})
        elif action == "prev":
            self.android._adb("shell", "input", "keyevent", "88")  # media previous
        elif action == "next":
            self.android._adb("shell", "input", "keyevent", "87")  # media next
        elif action == "zoom":
            self._send_hud_sync({"type": "transcript", "who": "ultron",
                                 "text": "Zoom acknowledged."})

    async def _handle_goal(self, text: str):
        if self.busy or not text:
            return
        self.busy = True
        self._send_hud_sync({"type": "transcript", "who": "user", "text": text})
        await self._send_hud({"type": "state", "state": "thinking"})
        try:
            self.run_task(text, self.max_steps)
        except KeyboardInterrupt:
            self._send_hud_sync({"type": "transcript", "who": "ultron", "text": "Stopped."})
        finally:
            self.busy = False
            await self._send_hud({"type": "state", "state": "idle"})

    def _send_hud_sync(self, m: dict):
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._send_hud(m), self.loop)

    async def _send_hud(self, m: dict):
        for ws in list(self.hud_clients):
            try:
                await ws.send(json.dumps(m))
            except Exception:
                self.hud_clients.discard(ws)

    def _check_kill(self):
        if os.path.exists(self.kill_file):
            raise KeyboardInterrupt("kill-switch")

    def run_task(self, goal: str, steps: int) -> dict:
        self.android.ensure()
        step_log = []  # renamed: was `log`, which shadowed the module-level log() fn
        last_sources: list = []
        for i in range(steps):
            self._check_kill()
            scene = self._perceive()
            hint = ""
            gl = (goal or "").lower()
            if any(h in gl for h in ("what is", "who is", "research", "find out",
                                     "latest", "look up")) or gl.strip().endswith("?"):
                hint = ("\nRESEARCH MODE: call {\"tool\": \"research\", \"args\": "
                        "{\"query\": \"" + goal + "\"}} first, then reply with a "
                        "summary ending in a 'Sources:' list.\n") if not last_sources else \
                       "\nRESEARCH MODE: research done - now reply with a summary plus a 'Sources:' list.\n"
            call = self.chat(
                f"Goal: {goal}\nStep {i+1}/{steps}\n{hint}Screen: {scene}\nNext single tool call?")
            tool = call.get("tool")
            if tool == "reply":
                txt = format_reply(call.get("args", {}).get("text", ""))
                if last_sources and "Sources:" not in txt:
                    txt = txt + "\n\nSources:\n" + "\n".join(f"- {s}" for s in last_sources)
                step_log.append({"reply": txt})
                self._speak(txt)
                self._send_hud_sync({"type": "transcript", "who": "ultron", "text": txt})
                break
            res = dispatch(call, self.ctrl)
            if tool == "research" and res.get("sources"):
                last_sources = list(res.get("sources") or [])
            step_log.append({"tool": tool, "res": res})
            if tool == "adb" and not res.get("ok") and "not-found" in str(res.get("reason", "")):
                break
        return {"goal": goal, "steps": len(step_log), "log": step_log}

    def _perceive(self) -> dict:
        root = self.android.dump_ui()
        if root is None:
            return {"mode": "C", "items": []}
        items = [n.get("text") or n.get("content-desc") or "" for n in root.iter("node")
                 if (n.get("text") or n.get("content-desc"))]
        return {"mode": "C", "items": items[:40]}

    def _speak(self, text: str):
        try:
            wav = self.tts.speak(text)
            if wav:
                os.system(f"play {wav} >/dev/null 2>&1 || true")
        except Exception:
            pass

    def status(self) -> dict:
        return {"device": CFG.device_name, "brain": CFG.mini_model,
                "linked": self.linked,
                "laptop": self.link.laptop if (self.link and self.linked) else None}

    async def serve(self):
        self.loop = asyncio.get_event_loop()
        async with websockets.serve(self.handler, "0.0.0.0", 8081):
            log("phone", {"event": "ws-up", "port": 8081})
            await asyncio.Future()

    # ---- native offline wake-word voice activation ----
    def _voice_state(self, s: str):
        """Mirror voice-listener state changes to the web HUD orb."""
        self._send_hud_sync({"type": "state", "state": s})

    def _voice_command(self, text: str):
        """Run a spoken command captured after the wake word (offline)."""
        if self.busy or not text:
            return
        self.busy = True
        try:
            self._send_hud_sync({"type": "transcript", "who": "user", "text": text})
            self._send_hud_sync({"type": "state", "state": "thinking"})
            self.run_task(text, self.max_steps)
        finally:
            self.busy = False
            self._send_hud_sync({"type": "state", "state": "idle"})

    def _on_heal_state(self, label: str, state: str, detail: str = ""):
        if state in ("recovering", "error"):
            self._send_hud_sync({"type": "state", "state": "recovering",
                                 "detail": f"{label}: {detail}"[:80]})
            log("phone", {"event": "heal", "label": label, "state": state, "detail": detail})

    def run(self):
        # start the mesh WebSocket server immediately (non-blocking) so the web
        # HUD + laptop bridge can connect without waiting on LAN discovery.
        import threading
        threading.Thread(target=self.connect_laptop, daemon=True).start()
        # continuous offline wake-word voice activation (background thread)
        if getattr(self, "voice", None):
            if self.voice.available:
                self.voice.start(self._voice_command, self._voice_state)
                log("phone", {"event": "voice-wake", "available": True})
            else:
                log("phone", {"event": "voice-wake", "available": False,
                              "note": "sounddevice/vosk missing on device"})
        # self-healing: watch the local brain; try to pull the mini model if absent
        if getattr(self, "watch", None):
            self.watch.add("ollama-mini",
                           lambda: check_ollama(CFG.mini_model)["reachable"],
                           recover=lambda: pull_ollama(CFG.mini_model))
            if getattr(self, "voice", None):
                v = self.voice
                self.watch.add("voice-mic", lambda: bool(v.available), recover=None)
            self.watch.start()
        if self.loop is None:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.serve())
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    a = PhoneAgent()
    print("local brain:", a.local.health())
    print("discover laptop:", a.connect_laptop())
    print("status:", a.status())
    # start the mesh WebSocket server (web HUD + laptop bridge connect here)
    try:
        a.run()
    except KeyboardInterrupt:
        print("\nstopped")
