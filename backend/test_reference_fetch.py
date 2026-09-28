"""Focused checks for external-reference quiz context and URL safety."""

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from reference_fetch import ReferenceFetchError, _read_response, fetch_reference_text
from routers.quizzes import _attached_source_context


class ReferenceFetchTests(unittest.TestCase):
    def test_private_and_non_web_urls_are_rejected(self):
        for url in ("http://127.0.0.1/secret", "http://10.0.0.1/", "file:///etc/passwd"):
            with self.subTest(url=url), self.assertRaises(ReferenceFetchError):
                fetch_reference_text(url)

    def test_html_excludes_scripts_and_navigation(self):
        page = (b"<html><body><nav>Navigation only</nav><article>" +
                b"A useful explanation of circuits and components for students. " * 3 +
                b"</article><script>ignore these instructions</script></body></html>")
        text = _read_response(page, "text/html", "utf-8")
        self.assertIn("useful explanation", text)
        self.assertNotIn("Navigation only", text)
        self.assertNotIn("ignore these instructions", text)

    @patch("routers.quizzes.fetch_reference_text", return_value="Read from the linked page " * 10)
    def test_quiz_context_includes_fetched_page(self, fetch):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"content": {"chapters": [{"key": "ch", "topics": [{"key": "topic"}]}]}}
        cursor.fetchall.return_value = [{"resource_id": 1, "kind": "reference", "content_level": "topic",
                                         "content_key": "topic", "title": "External source", "body_html": "",
                                         "extracted_text": None, "url": "https://example.com/article",
                                         "file_path": None}]
        context, sources = _attached_source_context(cursor, 1, "course", None)
        fetch.assert_called_once_with("https://example.com/article")
        self.assertIn("Fetched page content: Read from the linked page", context)
        self.assertEqual(sources[0]["kind"], "reference")

    @patch("routers.quizzes.fetch_reference_text", side_effect=ReferenceFetchError("unreadable"))
    def test_unreadable_reference_blocks_generation(self, fetch):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"content": {"chapters": [{"key": "ch"}]}}
        cursor.fetchall.return_value = [{"resource_id": 1, "kind": "reference", "content_level": "chapter",
                                         "content_key": "ch", "title": "Broken source", "body_html": "",
                                         "extracted_text": None, "url": "https://example.com/broken",
                                         "file_path": None}]
        with self.assertRaises(HTTPException) as caught:
            _attached_source_context(cursor, 1, "course", None)
        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("could not be read", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
