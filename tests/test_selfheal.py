"""Self-healing tests: supervisor restart, health watchdog, stuck-task repair."""
import sys, time, types
import unittest
from unittest import mock

sys.path.insert(0, "/root/jarvis-ultron/laptop/core")
import selfheal
from selfheal import Supervisor, HealthWatch, self_repair_stuck


class TestSupervisor(unittest.TestCase):
    def test_restarts_on_exception(self):
        calls = {"n": 0}
        def boom():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("boom")
            # 3rd run succeeds and returns
            return
        states = []
        s = Supervisor("t", boom, on_state=lambda n, st, d="": states.append(st),
                       base_delay=0.01, max_delay=0.05)
        # run target synchronously via the loop thread, but target returns after 3 tries
        s._loop()
        self.assertGreaterEqual(calls["n"], 3, "should have retried until success")
        self.assertIn("recovering", states)

    def test_no_restart_when_ok(self):
        calls = {"n": 0}
        def fine():
            calls["n"] += 1
            return  # clean exit
        s = Supervisor("t", fine, base_delay=0.01, max_delay=0.05)
        s._loop()
        self.assertEqual(calls["n"], 1)


class TestHealthWatch(unittest.TestCase):
    def test_recovers_on_failure(self):
        checks = {"up": True}
        recovered = []
        def check():
            return checks["up"]
        def recover():
            recovered.append(True)
            checks["up"] = True  # simulate fix
        states = []
        w = HealthWatch(interval=0.01, on_state=lambda s, d="": states.append((s, d)))
        w.add("svc", check, recover=recover)
        # first tick: down -> recover called
        checks["up"] = False
        w._tick()
        self.assertTrue(recovered, "recover should have been called when down")
        self.assertIn(("recovering", "svc down"), states)


class TestStuckRepair(unittest.TestCase):
    def test_aborts_stuck_task(self):
        st = {"running": True, "steps": 10, "last_progress_step": 2, "aborted": False}
        fixed = self_repair_stuck(st, max_idle_steps=5)
        self.assertTrue(fixed)
        self.assertFalse(st["running"])
        self.assertTrue(st["aborted"])

    def test_no_abort_when_progressing(self):
        st = {"running": True, "steps": 3, "last_progress_step": 2, "aborted": False}
        self.assertFalse(self_repair_stuck(st, max_idle_steps=5))
        self.assertTrue(st["running"])


if __name__ == "__main__":
    unittest.main()
