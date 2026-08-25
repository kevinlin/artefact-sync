from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import cli
from tests.helpers import make_repo, make_source_tree

NOTE = b"# Queue backlog\n\nSix hours of delay. Root cause below.\n"
PAGE = b"<html><head></head><body><h1>Cost model</h1></body></html>\n"
CLEAN_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="4" height="4"/></svg>\n'


class EndToEndTests(unittest.TestCase):
    def test_the_full_M1_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {
                "incident/queue-backlog.md": NOTE,
                "talk/cost-model.html": PAGE,
                "diagrams/flow.svg": CLEAN_SVG,
                "drafts/wip.md": b"# not ready\n",
                "notes.psd": b"binary",
            })
            pointer = root / "pointer.json"

            self.assertEqual(cli.EXIT_OK, cli.main(
                ["init", "--pointer", str(pointer), "--repo", str(repo), "--source", str(source)]))

            # First plan blocks: three approved sources have no entry yet.
            self.assertEqual(cli.EXIT_BLOCKED, cli.main(["plan", "--pointer", str(pointer)]))

            body = json.loads((repo / "artefacts" / "manifest.json").read_text())
            self.assertEqual(3, len(body["entries"]))
            sources = {e["source"] for e in body["entries"]}
            self.assertNotIn("drafts/wip.md", sources)   # ignored
            self.assertNotIn("notes.psd", sources)       # unsupported

            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))

            published = repo / "artefacts"
            self.assertTrue((published / "incident/queue-backlog/index.html").is_file())
            self.assertTrue((published / "talk/cost-model/index.html").is_file())
            self.assertTrue((published / "diagrams/flow.svg").is_file())

            # SVG is byte-identical: validated, never rewritten.
            self.assertEqual(CLEAN_SVG, (published / "diagrams/flow.svg").read_bytes())

            # Markdown survives the round trip.
            from render import extract_markdown

            page = (published / "incident/queue-backlog/index.html").read_text(encoding="utf-8")
            self.assertEqual(NOTE.decode("utf-8"), extract_markdown(page))

            # The catalogue links every entry.
            catalogue = (published / "index.html").read_text(encoding="utf-8")
            for href in ("incident/queue-backlog/", "talk/cost-model/", "diagrams/flow.svg"):
                self.assertIn(href, catalogue)

            self.assertEqual(cli.EXIT_OK, cli.main(["validate", "--pointer", str(pointer)]))

            # Convergent: a second sync changes nothing.
            before = {p: p.read_bytes() for p in sorted(published.rglob("*")) if p.is_file()}
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            after = {p: p.read_bytes() for p in sorted(published.rglob("*")) if p.is_file()}
            self.assertEqual(before, after)

    def test_a_dirty_svg_blocks_the_run_and_names_the_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"d/bad.svg": b"<svg>\n<script/>\n</svg>\n"})
            pointer = root / "pointer.json"
            cli.main(["init", "--pointer", str(pointer),
                      "--repo", str(repo), "--source", str(source)])
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["plan", "--pointer", str(pointer)])
                # The first run also blocks for the unlisted source, and writes its proposal.
                # The second run has the entry, so only the SVG itself can still block it.
                second = cli.main(["plan", "--pointer", str(pointer)])
            text = buffer.getvalue()
        self.assertEqual(cli.EXIT_BLOCKED, code)
        self.assertEqual(cli.EXIT_BLOCKED, second)
        blocked = text[text.index("BLOCKED"):]
        self.assertIn("d/bad.svg:2", blocked)
        self.assertIn("script element", blocked)

    def test_the_prior_art_repo_is_never_touched(self) -> None:
        import subprocess

        prior = Path("/Users/keli/dev/github-kevinlin/kevinlin.github.io")
        if not prior.is_dir():
            self.skipTest("prior art not present on this machine")
        result = subprocess.run(["git", "status", "--short"], cwd=prior,
                                capture_output=True, text=True)
        self.assertEqual("", result.stdout.strip())
