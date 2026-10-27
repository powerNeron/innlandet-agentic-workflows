"""Navigation must not turn expired or missing approvals into source access."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from hamar_agent.exam_links import main, navigation


class ExamLinksTests(unittest.TestCase):
    def test_no_file_or_network_access(self):
        with patch("builtins.open", side_effect=AssertionError("No file access")), \
                patch("pathlib.Path.open", side_effect=AssertionError("No catalog access")), \
                patch("socket.socket", side_effect=AssertionError("No network")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("No DNS")):
            self.assertEqual(len(navigation()["links"]), 8)

    def test_no_approval_or_model_claim(self):
        result = navigation()
        self.assertEqual(result["source_approval"], "not_asserted")
        self.assertFalse(result["municipal_content_loaded"])
        self.assertFalse(result["model_used"])
        self.assertNotIn("claims", result)

    def test_exact_official_reference_scope(self):
        links = navigation()["links"]
        self.assertEqual(len({x["source_id"] for x in links}), 8)
        for link in links:
            self.assertTrue(link["url"].startswith("https://www.hamar.kommune.no/"))
            self.assertEqual(set(link), {"source_id", "topic", "url"})

    def test_result_mutation_does_not_change_navigation(self):
        navigation()["links"][0]["url"] = "https://example.invalid/"
        self.assertTrue(navigation()["links"][0]["url"].startswith("https://www.hamar.kommune.no/"))

    def test_cli_outputs_explicit_mode(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(), 0)
        self.assertEqual(json.loads(output.getvalue())["mode"], "exam_links_only")
