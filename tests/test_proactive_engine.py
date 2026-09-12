"""Tests for proactive engine."""
import sys
import os
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "laptop", "core"))

from proactive_engine import (
    ProactiveEngine, ObservationResult, get_proactive_engine,
    UserMemory, GoogleWorkspace, DesktopAutomation
)


class TestProactiveEngineBasic(unittest.TestCase):
    def setUp(self):
        self.tmpdir = os.path.join(os.path.dirname(__file__), "..", "..", "tmp_test")
        os.makedirs(self.tmpdir, exist_ok=True)
        self.db_path = os.path.join(self.tmpdir, "memory.db")
        self.memory = UserMemory(self.db_path)
        self.engine = ProactiveEngine(self.memory)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_engine_initialization(self):
        self.assertIsNotNone(self.engine)
        self.assertIsNotNone(self.engine.memory)
        self.assertIsNotNone(self.engine.google_ws)

    def test_start_stop(self):
        self.engine.start()
        self.assertTrue(self.engine._running)
        self.engine.stop()
        self.assertFalse(self.engine._running)

    def test_context_hints(self):
        self.engine.set_context_hint("test_key", "test_value")
        ctx = self.engine.get_current_context()
        self.assertIn("test_key", ctx)
        self.assertEqual(ctx["test_key"], "test_value")

    def test_add_observation(self):
        self.engine.add_observation("test_type", {"data": "test"}, actionable=False)
        # Should not raise

    def test_get_suggested_actions(self):
        actions = self.engine.get_suggested_actions()
        self.assertIsInstance(actions, list)


class TestObservationResult(unittest.TestCase):
    def test_creation(self):
        result = ObservationResult(
            type="calendar", timestamp="2024-01-01T10:00:00",
            data={"event": "test"}, actionable=True,
            suggested_action={"type": "prepare"}
        )
        self.assertEqual(result.type, "calendar")
        self.assertTrue(result.actionable)
        self.assertEqual(result.suggested_action["type"], "prepare")


class TestGoogleObservation(unittest.TestCase):
    def test_calendar_observation(self):
        from proactive_engine import ProactiveEngine, UserMemory, GoogleWorkspace

        # Setup mock Google Workspace
        mock_ws = mock.MagicMock()
        mock_ws.calendar.list_events.return_value = [
            {
                "summary": "Team Meeting",
                "start": {"dateTime": "2099-01-15T10:00:00"},
                "duration": {"dateMinutes": 60},
                "location": "Conference Room",
                "attendees": [{"email": "user@example.com"}]
            }
        ]
        mock_ws.gmail.list_messages.return_value = []

        mock_auth = mock.MagicMock()
        mock_auth.get_credentials.return_value = mock.MagicMock()
        mock_ws.auth = mock_auth

        import tempfile
        memory_path = os.path.join(tempfile.gettempdir(), "ultron_proactive_calendar_test.db")
        memory = UserMemory(memory_path)
        engine = ProactiveEngine(memory, google_ws=mock.MagicMock(), desktop=mock.MagicMock())
        engine.google_ws = mock_ws
        import asyncio
        result = asyncio.run(engine._observe("calendar"))
        self.assertEqual(result.type, "calendar")
        self.assertTrue(result.actionable)
        self.assertIsNotNone(result.suggested_action)
        try:
            os.remove(memory_path)
        except OSError:
            pass


class TestSuggestions(unittest.TestCase):
    @mock.patch("proactive_engine.datetime")
    def test_morning_suggestion(self, mock_datetime):
        # Setup time to be morning
        mock_now = mock.MagicMock()
        mock_now.hour = 8
        mock_now.minute = 0
        type(mock_datetime).now = mock.PropertyMock(return_value=mock_now)

        engine = ProactiveEngine.__new__(ProactiveEngine)
        engine.current_context = {}
        engine.google_ws = mock.MagicMock()
        engine._is_soon_to_meet = lambda now: False

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            # Mock the google workspace
            mock_ws = engine.google_ws
            mock_ws.calendar.list_events.return_value = []
            mock_ws.gmail.list_messages.return_value = []

            result = loop.run_until_complete(
                engine._generate_suggestion(mock_now)
            )
            self.assertEqual(result.type, "suggestion")
            self.assertTrue(result.actionable)
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)