"""Fail-closed ingestion entrypoint regressions; no municipal network access."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hamar_agent.portal_sources import main


class SnapshotImportPrivacyTests(unittest.TestCase):
    def test_raw_snapshot_command_fails_before_open_or_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "unreviewed.html"
            snapshot.write_text("Synthetic non-personal test text", encoding="utf-8")
            output = root / "catalog.json"
            original_open = Path.open

            def refuse_snapshot(path, *args, **kwargs):
                if path == snapshot:
                    raise AssertionError("raw HTML snapshot must not be opened")
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", new=refuse_snapshot), \
                    redirect_stderr(StringIO()), self.assertRaises(SystemExit) as raised:
                main(["import-snapshot", "--source-id", "synthetic-test", "--snapshot", str(snapshot),
                      "--output", str(output)])

            self.assertEqual(raised.exception.code, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
