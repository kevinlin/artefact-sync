from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from artefact_sync import cli
from tests.helpers import make_repo, make_source_tree

NOTE = b"# Cost model\n\nBuild versus buy, with the numbers.\n"


class AddLoopTests(unittest.TestCase):
    def test_add_then_delete_then_converge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {})
            inbox = root / "inbox"
            inbox.mkdir()
            (inbox / "Cost Model.md").write_bytes(NOTE)
            (inbox / "Client Curve.png").write_bytes(b"PNGDATA")
            pointer = root / "pointer.json"
            self.assertEqual(cli.EXIT_OK, cli.main(
                ["init", "--pointer", str(pointer), "--repo", str(repo), "--source", str(source)]))

            # add renders the Markdown page, links it, and needs no prior plan run.
            self.assertEqual(cli.EXIT_OK, cli.main(
                ["add", str(inbox / "Cost Model.md"), "--pointer", str(pointer), "--yes"]))
            published = repo / "artefacts"
            page = (published / "cost-model" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Build versus buy", page)
            self.assertIn("cost-model/", (published / "index.html").read_text(encoding="utf-8"))
            body = json.loads((published / "manifest.json").read_text())
            self.assertEqual(["general"], [c["id"] for c in body["collections"]])

            # A private-looking name warns, next to its URL, and still publishes.
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["add", str(inbox / "Client Curve.png"),
                                 "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_OK, code)
            self.assertIn('filename contains "client"', buffer.getvalue())
            self.assertTrue((published / "client-curve.png").is_file())

            # Deleting the source deletes the file, and says nothing about orphans.
            (source / "Client Curve.png").unlink()
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["sync", "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_OK, code)
            self.assertNotIn("orphan", buffer.getvalue())
            self.assertFalse((published / "client-curve.png").exists())

            self.assertEqual(cli.EXIT_OK, cli.main(["validate", "--pointer", str(pointer)]))

            # Convergent: a second sync changes nothing.
            before = {path: path.read_bytes()
                      for path in sorted(published.rglob("*")) if path.is_file()}
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            after = {path: path.read_bytes()
                     for path in sorted(published.rglob("*")) if path.is_file()}
            self.assertEqual(before, after)

    def test_add_reports_excluded_files_it_did_not_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"notes.psd": b"binary", "drafts/wip.md": b"# w\n"})
            inbox = root / "inbox"
            inbox.mkdir()
            (inbox / "curve.png").write_bytes(b"PNGDATA")
            pointer = root / "pointer.json"
            cli.main(["init", "--pointer", str(pointer),
                      "--repo", str(repo), "--source", str(source)])
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["add", str(inbox / "curve.png"),
                                 "--pointer", str(pointer), "--yes"])
            text = buffer.getvalue()
            self.assertTrue((repo / "artefacts" / "curve.png").is_file())
        self.assertEqual(cli.EXIT_OK, code)
        self.assertIn("EXCLUDED", text)
        self.assertIn(".psd", text)
        self.assertIn("drafts/", text)
