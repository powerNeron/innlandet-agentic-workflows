"""Offline storage and CLI contract tests using synthetic data only."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from hamar_agent.__main__ import main
from hamar_agent.schemas import Result
from hamar_agent.sources import APPROVED_SOURCES, load_source
from hamar_agent.storage import save_result
from hamar_agent.summarize import MockSummarizer

FIXTURE = APPROVED_SOURCES["synthetic-water-demo"].path


class StorageTests(unittest.TestCase):
    def setUp(self):
        source = load_source("synthetic-water-demo")
        self.result = Result(source, MockSummarizer().summarize(source))

    def test_save_utf8_json_and_return_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            self.assertEqual(save_result(self.result, path), path)
            raw = path.read_bytes()
            self.assertEqual(raw, self.result.to_json().encode("utf-8"))
            self.assertNotIn(b"\r\n", raw)
            self.assertEqual(json.loads(raw), json.loads(self.result.to_json()))

    def test_existing_files_including_empty_are_preserved(self):
        for existing in (b"", b"existing synthetic content"):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "result.json"
                path.write_bytes(existing)
                with self.assertRaises(FileExistsError):
                    save_result(self.result, path)
                self.assertEqual(path.read_bytes(), existing)

    def test_missing_parent_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing" / "result.json"
            with self.assertRaises(FileNotFoundError):
                save_result(self.result, path)
            self.assertFalse(path.parent.exists())

    def test_directory_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(OSError):
                save_result(self.result, Path(directory))
            self.assertTrue(Path(directory).is_dir())

    def test_permission_error_propagates(self):
        with patch.object(Path, "open", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                save_result(self.result, Path("result.json"))

    def test_write_failure_propagates_without_deletion(self):
        stream = MagicMock()
        stream.__enter__.return_value.write.side_effect = OSError("disk full")
        with patch.object(Path, "open", return_value=stream) as opened:
            with self.assertRaisesRegex(OSError, "disk full"):
                save_result(self.result, Path("result.json"))
        opened.assert_called_once_with("x", encoding="utf-8", newline="\n")
        stream.__exit__.assert_called_once()

    def test_serialization_failure_does_not_open_destination(self):
        with patch.object(Result, "to_json", side_effect=ValueError("serialization failed")):
            with patch.object(Path, "open") as opened:
                with self.assertRaises(ValueError):
                    save_result(self.result, Path("result.json"))
                opened.assert_not_called()

    def test_encoding_failure_does_not_open_destination(self):
        with patch.object(Result, "to_json", return_value="\ud800"):
            with patch.object(Path, "open") as opened:
                with self.assertRaises(UnicodeEncodeError):
                    save_result(self.result, Path("result.json"))
                opened.assert_not_called()

    def test_cli_without_output_does_not_save(self):
        output = io.StringIO()
        with patch("hamar_agent.__main__.save_result") as save, redirect_stdout(output):
            self.assertEqual(main(["--fixture", str(FIXTURE)]), 0)
        save.assert_not_called()
        self.assertEqual(output.getvalue(), self.result.to_json())

    def test_cli_save_matches_unchanged_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            output, error = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                self.assertEqual(main(["--fixture", str(FIXTURE), "--output", str(path)]), 0)
            self.assertEqual(path.read_text(encoding="utf-8"), output.getvalue())
            self.assertEqual(json.loads(output.getvalue()), json.loads(self.result.to_json()))
            self.assertEqual(error.getvalue(), "")

    def test_cli_duplicate_fails_without_stdout_or_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_bytes(b"keep")
            self.assert_cli_save_error(path)
            self.assertEqual(path.read_bytes(), b"keep")

    def assert_cli_save_error(self, path):
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error), self.assertRaises(SystemExit) as raised:
            main(["--fixture", str(FIXTURE), "--output", str(path)])
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("Unable to save or serialize result", error.getvalue())

    def test_cli_missing_parent_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assert_cli_save_error(Path(directory) / "missing" / "result.json")

    def test_cli_write_failure_fails_cleanly(self):
        with patch("hamar_agent.__main__.save_result", side_effect=OSError("disk full")):
            self.assert_cli_save_error(Path("result.json"))

    def test_cli_serialization_failure_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            with patch.object(Result, "to_json", side_effect=ValueError("bad JSON")):
                self.assert_cli_save_error(path)
            self.assertFalse(path.exists())
