"""Tests for the persistent memory system."""
import sys
import os
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "laptop", "core"))

from memory import UserMemory, SessionContext, Fact, SessionSummary, MemoryConsolidator


class TestUserMemory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_memory.db")
        self.memory = UserMemory(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_set_and_get_fact(self):
        fact = self.memory.set_fact("preference", "coffee", "black, no sugar")
        self.assertEqual(fact.category, "preference")
        self.assertEqual(fact.key, "coffee")
        self.assertEqual(fact.value, "black, no sugar")

        retrieved = self.memory.get_fact("preference", "coffee")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.value, "black, no sugar")

    def test_update_fact(self):
        self.memory.set_fact("preference", "coffee", "black")
        fact = self.memory.set_fact("preference", "coffee", "with milk")
        self.assertEqual(fact.value, "with milk")

    def test_get_facts_by_category(self):
        self.memory.set_fact("preference", "coffee", "black")
        self.memory.set_fact("preference", "tea", "green")
        self.memory.set_fact("person", "mom", "Jane")

        prefs = self.memory.get_facts("preference")
        self.assertEqual(len(prefs), 2)

        all_facts = self.memory.get_facts()
        self.assertEqual(len(all_facts), 3)

    def test_search_facts(self):
        self.memory.set_fact("preference", "coffee", "black, no sugar")
        self.memory.set_fact("person", "mom", "Jane Doe")

        results = self.memory.search_facts("coffee")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].key, "coffee")

        results = self.memory.search_facts("jane")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].key, "mom")

    def test_delete_fact(self):
        self.memory.set_fact("preference", "coffee", "black")
        self.assertTrue(self.memory.delete_fact("preference", "coffee"))
        self.assertIsNone(self.memory.get_fact("preference", "coffee"))
        self.assertFalse(self.memory.delete_fact("preference", "coffee"))

    def test_session_save_and_load(self):
        summary = SessionSummary(
            session_id="test123",
            started_at="2024-01-01T10:00:00",
            goals=["test goal"],
            key_facts_learned=["learned something"],
            decisions_made=["decided something"],
            pending_actions=["do something"],
            mood="happy",
            summary="Test session"
        )
        self.memory.save_session(summary)

        loaded = self.memory.get_latest_session()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.session_id, "test123")
        self.assertEqual(loaded.goals, ["test goal"])
        self.assertEqual(loaded.mood, "happy")

    def test_session_persistence(self):
        # Create a session context, add data, persist
        ctx = SessionContext(self.memory)
        ctx.add_goal("Test goal")
        ctx.add_fact_learned("Learned fact")
        ctx.add_decision("Made decision")
        ctx.add_pending("Pending action")
        ctx.set_mood("focused")
        ctx.set_topic("Testing")
        ctx.add_exchange("user", "Hello")
        ctx.add_exchange("assistant", "Hi there")

        ctx.persist()

        loaded = self.memory.get_latest_session()
        self.assertIsNotNone(loaded)
        self.assertIn("Test goal", loaded.goals)
        self.assertIn("Learned fact", loaded.key_facts_learned)
        self.assertIn("Made decision", loaded.decisions_made)
        self.assertIn("Pending action", loaded.pending_actions)


class TestSessionContext(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_memory.db")
        self.memory = UserMemory(self.db_path)
        self.ctx = SessionContext(self.memory)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_exchange(self):
        self.ctx.add_exchange("user", "Hello")
        self.ctx.add_exchange("assistant", "Hi")
        self.assertEqual(len(self.ctx.conversation_history), 2)

    def test_context_for_prompt(self):
        self.ctx.add_goal("Test goal")
        self.ctx.add_fact_learned("Test fact")
        self.ctx.add_exchange("user", "Hello")
        ctx_str = self.ctx.get_context_for_prompt()
        self.assertIn("Test goal", ctx_str)
        self.assertIn("Test fact", ctx_str)
        self.assertIn("Hello", ctx_str)

    def test_history_limit(self):
        for i in range(60):
            self.ctx.add_exchange("user", f"Message {i}")
        self.assertEqual(len(self.ctx.conversation_history), 50)


class TestMemoryConsolidator(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_memory.db")
        self.memory = UserMemory(self.db_path)
        self.consolidator = MemoryConsolidator(self.memory)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_extract_preferences(self):
        ctx = SessionContext(self.memory)
        ctx.add_exchange("user", "I like black coffee")
        ctx.add_exchange("assistant", "Noted")
        ctx.add_exchange("user", "My favorite color is blue")

        facts = self.consolidator.consolidate_session(ctx)
        self.assertTrue(len(facts) > 0)

        # Check if preferences were extracted
        coffee_fact = self.memory.get_fact("preference", "black_coffee")
        self.assertIsNotNone(coffee_fact)

    def test_extract_people(self):
        ctx = SessionContext(self.memory)
        ctx.add_exchange("user", "My mom is named Sarah")
        ctx.add_exchange("assistant", "Nice to meet her")

        facts = self.consolidator.consolidate_session(ctx)
        mom_fact = self.memory.get_fact("person", "mom")
        self.assertIsNotNone(mom_fact)
        self.assertEqual(mom_fact.value, "Sarah")


if __name__ == "__main__":
    unittest.main(verbosity=2)