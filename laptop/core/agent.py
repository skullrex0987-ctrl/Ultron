"""Autonomous agent loop with per-task step prompt (Q17/21 C: full auto,
NO cap, but MUST ask the user for step count before every task) and a
global kill-switch + hard ceiling.

The loop is a real perceive -> decide -> act -> verify cycle so the agent
actually accomplishes goals on the linked phone / local machine, not just
emits one tool call.
"""
from __future__ import annotations
import os
from typing import Callable, Optional

from config import CFG
from audit import log, transcript
from ollama_client import BrainClient
from tools import dispatch
from android_control import AndroidControl
from perception import perceive


class KillSwitch(Exception):
    pass


def _check_kill() -> None:
    if os.path.exists(CFG.kill_switch_file):
        raise KillSwitch(f"kill-switch file present: {CFG.kill_switch_file}")


class Agent:
    def __init__(self, model_side: str = "main",
                 on_reply: Optional[Callable[[str], None]] = None):
        self.llm = BrainClient(model=CFG.model_for(model_side))
        self.android = AndroidControl()
        self.max_steps = CFG.max_step_hard_cap
        self._prompt_fn = None
        self.on_reply = on_reply  # callback(text) -> e.g. trigger TTS on HUD

    def ask_steps(self, goal: str) -> int:
        """Q21: always prompt the user for number of steps before a task."""
        n = CFG.max_step_hard_cap
        if self._prompt_fn:
            try:
                val = self._prompt_fn(f"How many steps for: {goal}? ")
                n = int(val) if val else CFG.max_step_hard_cap
            except (ValueError, TypeError):
                n = CFG.max_step_hard_cap
        else:
            log("agent", {"event": "step-prompt-default", "goal": goal,
                          "steps": n})
        n = min(max(1, n), CFG.max_step_hard_cap)
        log("agent", {"event": "step-prompt", "goal": goal, "steps": n})
        return n

    def set_prompt(self, fn: Callable[[str], str]) -> None:
        self._prompt_fn = fn

    def _decide(self, goal: str, step: int, steps: int, scene: dict) -> dict:
        ctx = (
            f"Goal: {goal}\n"
            f"Step {step+1}/{steps}\n"
            f"Current screen/context: {scene}\n"
            "Decide the SINGLE next tool call to make progress. "
            "If the goal is fully achieved, respond with tool 'reply' summarizing. "
            "If you need the phone unlocked first and it's locked, use adb 'keyevent 82' then 'swipe'. "
            "Prefer adb 'find \"<text>\"' to tap visible UI by name."
        )
        return self.llm.chat(ctx)

    def run(self, goal: str, perception_mode: str = "C") -> dict:
        _check_kill()
        steps = self.ask_steps(goal)
        log("agent", {"event": "start", "goal": goal, "steps": steps})
        transcript(f"Starting: {goal} (max {steps} steps)", who="ultron")

        self.android.connect()
        results = []
        for i in range(steps):
            _check_kill()
            scene = perceive(self.android, perception_mode)
            try:
                call = self._decide(goal, i, steps, scene)
            except Exception as e:  # noqa
                log("agent", {"event": "llm-error", "err": str(e)})
                results.append({"step": i, "error": str(e)})
                break

            tool = call.get("tool")
            if tool == "reply":
                text = call.get("args", {}).get("text", "")
                transcript(text, who="ultron")
                if self.on_reply:
                    self.on_reply(text)
                results.append({"step": i, "reply": text})
                break

            # route through tools; adb needs the android handle
            res = dispatch(call, android=self.android)
            ok = res.get("ok", False)
            log("agent", {"event": "step-done", "tool": tool,
                          "ok": ok, "res": res})
            results.append({"step": i, "tool": tool, "res": res})

            # verify: after a UI action, confirm the expected element is present
            if tool == "adb":
                cmd = str(call.get("args", {}).get("cmd", ""))
                if "find" in cmd and ok:
                    target = cmd.split('"')[1] if '"' in cmd else ""
                    if target and not self.android.reached(target):
                        log("agent", {"event": "verify-failed", "target": target})
                        transcript(f"Tapped '{target}' but it's not confirmed on screen.", who="ultron")
                if "not-found" in str(res.get("reason", "")):
                    transcript(f"Could not find UI element: {res.get('reason')}", who="ultron")

        transcript("Task complete.", who="ultron")
        return {"goal": goal, "steps_run": len(results), "results": results}
