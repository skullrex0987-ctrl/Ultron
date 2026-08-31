"""Tests for structured output formatting (format_reply) and RESEARCH mode.

No network: research() is exercised with a monkeypatched web_fetch.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "laptop", "core"))

import tools as T
from tools import format_reply, research, dispatch, TOOL_DOCS


class TestFormatReply(unittest.TestCase):
    def test_messy_string_cleaned(self):
        messy = (
            "<think>internal chain of thought here</think>\n"
            "# Result\n"
            "\n\n\n\n"
            "* first bullet\n"
            "\u2022 second bullet\n"
            "[system] noise line\n"
            "\n\n\n"
            "done   \n"
        )
        out = format_reply(messy)
        self.assertNotIn("<think>", out)
        self.assertNotIn("internal chain of thought", out)
        self.assertNotIn("[system]", out)
        self.assertNotIn("\n\n\n", out)          # 3+ blank lines collapsed
        self.assertIn("# Result", out)            # headings kept
        self.assertIn("- first bullet", out)      # bullets normalized
        self.assertIn("- second bullet", out)
        self.assertIn("noise line", out)
        self.assertTrue(out.endswith("done"))     # trailing ws stripped

    def test_idempotent_and_safe(self):
        self.assertEqual(format_reply(""), "")
        self.assertEqual(format_reply(None), "")
        s = "- a\n\n- b"
        self.assertEqual(format_reply(format_reply(s)), format_reply(s))
        self.assertEqual(format_reply(s), s)

    def test_plain_text_unchanged(self):
        self.assertEqual(format_reply("hello world"), "hello world")


SEARCH_HTML = (
    '<a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Fpage1">One</a>'
    '<a class="result__a" href="https://example.org/page2">Two</a>'
)


def _fake_web_fetch(url):
    if "duckduckgo" in url:
        return {"ok": True, "content": SEARCH_HTML}
    return {"ok": True, "content": "<html><body><p>Answer body for %s</p></body></html>" % url}


class TestResearch(unittest.TestCase):
    def test_research_returns_sources(self):
        with mock.patch.object(T, "web_fetch", _fake_web_fetch):
            r = research("what is ultron")
        self.assertIsInstance(r, dict)
        self.assertIn("sources", r)
        self.assertIn("answer", r)
        self.assertTrue(r["ok"])
        self.assertIsInstance(r["sources"], list)
        self.assertTrue(any("example.com/page1" in s for s in r["sources"]))
        self.assertTrue(any("example.org/page2" in s for s in r["sources"]))
        self.assertIn("Sources:", r["answer"])
        self.assertIn("Answer body", r["answer"])

    def test_research_direct_url(self):
        with mock.patch.object(T, "web_fetch", _fake_web_fetch):
            r = research("https://example.net/doc")
        self.assertEqual(r["sources"], ["https://example.net/doc"])
        self.assertIn("Sources:", r["answer"])

    def test_research_empty_query(self):
        r = research("")
        self.assertFalse(r["ok"])
        self.assertEqual(r["sources"], [])

    def test_dispatch_routes_research(self):
        with mock.patch.object(T, "web_fetch", _fake_web_fetch):
            r = dispatch({"tool": "research", "args": {"query": "latest news"}})
        self.assertIn("sources", r)
        self.assertIn("research", TOOL_DOCS)


class TestPhoneMirror(unittest.TestCase):
    def test_phone_tools_have_research_and_format(self):
        p = os.path.join(os.path.dirname(__file__), "..", "phone", "agent",
                         "tools_phone.py")
        with open(p, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("def research(", src)
        self.assertIn("def format_reply(", src)
        self.assertIn('n == "research"', src)


if __name__ == "__main__":
    unittest.main()
