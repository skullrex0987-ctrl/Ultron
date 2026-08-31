#!/usr/bin/env python3
"""Standalone ULTRON laptop wake-word sender (offline voice only).

Runs ONLY the offline voice activation (Vosk + sounddevice microphone) and,
when the wake word "ultron" is heard followed by a spoken command, forwards that
command to the running ULTRON core over WebSocket at ws://127.0.0.1:8766 as a
{type: "goal", goal: <text>} message.

This is intentionally dependency-light and self-contained:
  - imports the laptop VoiceListener from laptop/core/stt_tts.py (adds laptop/core
    to sys.path automatically)
  - connects a websocket client (websockets) to the core

If the offline voice stack (sounddevice / vosk) or the core is unavailable, it
prints a friendly note instead of crashing.

Usage:
    python laptop/wake_ultron.py
"""
from __future__ import annotations
import os
import sys
import json
import asyncio

HERE = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(HERE, "core")
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

CORE_WS = "ws://127.0.0.1:8766"


async def main() -> None:
    # Import the laptop VoiceListener (graceful if deps missing).
    try:
        from stt_tts import VoiceListener
    except Exception as e:  # pragma: no cover
        print("Could not import VoiceListener from laptop/core/stt_tts.py:", e)
        return

    vl = VoiceListener()
    if not vl.available:
        print("Offline voice (Vosk / sounddevice) is not available on this machine.")
        print("Install with:  pip install vosk sounddevice websockets  (and numpy)")
        return

    try:
        import websockets  # noqa: F401
    except Exception:
        print("The 'websockets' package is required to talk to the ULTRON core.")
        print("Install with:  pip install websockets")
        return

    loop = asyncio.get_event_loop()
    queue: "asyncio.Queue[str]" = asyncio.Queue()

    def on_command(text: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, text)

    def on_state(state: str) -> None:
        print(f"[voice] {state}", flush=True)

    # Background WS sender: one persistent connection, reconnects if dropped.
    async def sender() -> None:
        ws = None
        while True:
            text = await queue.get()
            if ws is None:
                try:
                    ws = await websockets.connect(CORE_WS)
                    print(f"[link] connected to ULTRON core at {CORE_WS}")
                except Exception:
                    print(f"[note] ULTRON core not running at {CORE_WS} yet — "
                          f"start it and speak again. (skipped: {text!r})")
                    ws = None
                    continue
            try:
                await ws.send(json.dumps({"type": "goal", "goal": text}))
                print(f"[sent] {text}")
            except Exception:
                print(f"[note] lost connection to ULTRON core; skipped: {text!r}")
                ws = None

    sender_task = asyncio.ensure_future(sender())

    print("[wake] ULTRON offline voice activation started. Say \"ultron\" then your command.")
    print(f"[wake] Commands forward to {CORE_WS} (type 'goal'). Ctrl-C to stop.")

    try:
        # VoiceListener.run() is blocking -> run it in its own thread.
        vl.start(on_command, on_state)
        # Keep the event loop alive while the listener thread runs.
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[wake] stopping…")
    finally:
        vl.stop()
        sender_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
