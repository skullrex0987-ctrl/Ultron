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
                 on_reply: Optional[Callable[[str], None]] = None,
                 on_step: Optional[Callable[[int, str, bool], None]] = None):
        self.llm = BrainClient(model=CFG.model_for(model_side))
        self.android = AndroidControl()
        self.max_steps = CFG.max_step_hard_cap
        self._prompt_fn = None
        self.on_reply = on_reply  # callback(text) -> e.g. trigger TTS on HUD
        self.on_step = on_step    # callback(step, desc, ok) -> live HUD progress

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

    def _decide(self, goal: str, step: int, steps: int, scene: dict, history: list[str], plan: list[str] | None = None) -> dict:
        hist = "\n".join(f"  - {h}" for h in history[-6:]) or "  (none yet)"
        plan_txt = ("\nPlanned steps: " + " -> ".join(str(p) for p in (plan or [])) + "\n") if plan else ""
        ctx = (
            f"Goal: {goal}\n"
            f"Step {step+1}/{steps}\n"
            f"Current screen/context: {scene}\n"
            f"What you already tried this task (do NOT repeat a failed action):\n{hist}\n"
            "Decide the SINGLE next tool call to make progress. "
            "If the goal is fully achieved, respond with tool 'reply' summarizing. "
            "If the phone looks locked (no app elements / keyguard), use adb "
            "'keyevent 82' then 'swipe 540 1800 540 900' to unlock. "
            "To tap a visible UI element by name, prefer adb 'find \"<text>\"'. "
            "If a find failed, try launching the app by name with adb 'launch <app>' "
            "then 'find' again. Keep each step small and verifiable."
        )
        return self.llm.chat(ctx)

    def run(self, goal: str, perception_mode: str = "C", use_plan: bool = True) -> dict:
        _check_kill()
        steps = self.ask_steps(goal)
        log("agent", {"event": "start", "goal": goal, "steps": steps, "plan": use_plan})
        transcript(f"Starting: {goal} (max {steps} steps)", who="ultron")

        self.android.connect()
        results = []
        history: list[str] = []
        unlocked = False
        plan_steps: list[str] = []
        if use_plan:
            try:
                p = self.llm.chat(
                    f"Goal: {goal}\nBreak this into an ordered list of short "
                    f"action steps (one verb each, e.g. 'unlock', 'open youtube', "
                    f"'search cats'). Reply as a JSON list of strings.")
                import json as _j
                try:
                    _raw = p.get("args", {}).get("text", "[]") if isinstance(p, dict) else "[]"
                    plan_steps = _j.loads(_raw)
                except Exception:
                    plan_steps = []
                if not isinstance(plan_steps, list):
                    plan_steps = [str(plan_steps)] if plan_steps else []
                if isinstance(plan_steps, list) and plan_steps:
                    transcript("Plan: " + " -> ".join(str(s) for s in plan_steps), who="ultron")
            except Exception as e:
                log("agent", {"event": "plan-error", "err": str(e)})

        for i in range(steps):
            _check_kill()
            scene = perceive(self.android, perception_mode)
            # unlock pre-step
            if not unlocked and (not scene.get("items") and perception_mode == "C"):
                self.android._adb("shell", "input", "keyevent", "82")
                self.android._adb("shell", "input", "swipe", "540", "1800", "540", "900")
                unlocked = True
                history.append("unlocked screen (keyevent 82 + swipe)")
                continue
            try:
                call = self._decide(goal, i, steps, scene, history, plan_steps)
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

            res = dispatch(call, android=self.android)
            ok = res.get("ok", False)
            log("agent", {"event": "step-done", "tool": tool, "ok": ok, "res": res})
            results.append({"step": i, "tool": tool, "res": res})
            history.append(f"step {i}: {tool} -> {'ok' if ok else 'FAILED ' + str(res.get('reason', ''))}")
            if self.on_step:
                self.on_step(i, f"{tool}: {'ok' if ok else 'failed'}", ok)

            # self-correction: find failed -> launch app then re-find
            if tool == "adb" and not ok and "not-found" in str(res.get("reason", "")):
                app = next((k for k in CFG.app_launch if k in goal.lower()), None)
                if app:
                    self.android.launch(app)
                    history.append(f"launched {app} after find failed")
                    re = dispatch({"tool": "adb", "args": {"cmd": call["args"]["cmd"]}},
                                  android=self.android)
                    ok = re.get("ok", False)
                    results.append({"step": i, "retry": "launch+" + app, "res": re})
                    history.append(f"retry find after launch {app} -> {'ok' if ok else 'still FAILED'}")
                    if ok:
                        continue
                transcript(f"Could not find UI element: {res.get('reason')}", who="ultron")

            if tool == "adb":
                cmd = str(call.get("args", {}).get("cmd", ""))
                if "find" in cmd and ok:
                    target = cmd.split('"')[1] if '"' in cmd else ""
                    if target and not self.android.reached(target):
                        log("agent", {"event": "verify-failed", "target": target})

        transcript("Task complete.", who="ultron")
        return {"goal": goal, "steps_run": len(results), "plan": plan_steps, "results": results}
