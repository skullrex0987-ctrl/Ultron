"""Autonomous agent loop with per-task step prompt (Q17/21 C: full auto,
NO cap, but MUST ask the user for step count before every task) and a
global kill-switch + hard ceiling.
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
    def __init__(self, model_side: str = "main"):
        self.llm = BrainClient(model=CFG.model_for(model_side))
        self.android = AndroidControl()
        self.max_steps = CFG.max_step_hard_cap
        self._prompt_fn = None  # set via set_prompt for interactive step count

    def ask_steps(self, goal: str) -> int:
        """Q21: always prompt the user for number of steps before a task.
        If no prompt fn injected (headless), default to the hard cap but LOG the ask."""
        n = CFG.max_step_hard_cap
        if self._prompt_fn:
            try:
                val = self._prompt_fn(f"How many steps for: {goal}? ")
                n = int(val) if val else CFG.max_step_hard_cap
            except (ValueError, TypeError):
                n = CFG.max_step_hard_cap
        else:
            n = CFG.max_step_hard_cap
        n = min(max(1, n), CFG.max_step_hard_cap)
        log("agent", {"event": "step-prompt", "goal": goal, "steps": n})
        return n

    def set_prompt(self, fn: Callable[[str], str]) -> None:
        self._prompt_fn = fn

    def run(self, goal: str, perception_mode: str = "C") -> dict:
        _check_kill()
        steps = self.ask_steps(goal)
        log("agent", {"event": "start", "goal": goal, "steps": steps})
        transcript(f"Starting: {goal} (max {steps} steps)", who="ultron")

        self.android.connect()
        results = []
        for i in range(steps):
            _check_kill()
            # perceive
            scene = perceive(self.android, perception_mode)
            ctx = f"Goal: {goal}\nStep {i+1}/{steps}\nScene: {scene}\nWhat is the next tool call?"
            try:
                call = self.llm.chat(ctx)
            except Exception as e:  # noqa
                log("agent", {"event": "llm-error", "err": str(e)})
                results.append({"step": i, "error": str(e)})
                break
            if call.get("tool") == "reply":
                transcript(call["args"].get("text", ""), who="ultron")
                results.append({"step": i, "reply": call["args"].get("text")})
                break
            # route through tools; 'adb' tool delegates to android control
            if call.get("tool") == "adb":
                res = getattr(self.android, "tap" if "tap" in str(call) else "_adb")(
                    *[]) if False else self.android._adb(*call["args"].get("cmd", "").split())
                results.append({"step": i, "tool": "adb", "res": res.returncode})
            else:
                res = dispatch(call)
                results.append({"step": i, "tool": call.get("tool"), "res": res})
            log("agent", {"event": "step-done", "step": i, "tool": call.get("tool")})
        transcript("Task complete.", who="ultron")
        return {"goal": goal, "steps_run": len(results), "results": results}
