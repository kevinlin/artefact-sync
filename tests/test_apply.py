from __future__ import annotations

import string
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from artefact_sync import apply as a
from artefact_sync.config import Context, site_from_dict
from artefact_sync.errors import ValidationError
from artefact_sync.manifest import Entry, resolve_within


class RoundTripVerificationTests(unittest.TestCase):
    def test_passes_when_the_embedded_markdown_matches_the_source(self) -> None:
        from artefact_sync import render

        entry = Entry(
            id="e", source=PurePosixPath("a.md"),
            destination=PurePosixPath("a/index.html"), title="A",
            collection="c", order=10, replacements={},
        )
        template = string.Template("<html>$block_start$markdown$block_end</html>")
        rendered = render.render_markdown_page(
            entry,
            b"# x\n",
            PurePosixPath("vendor/marked.min.js"),
            site_from_dict({"base_url": "https://x.example/artefacts/"}),
            template,
        )
        self.assertIsNone(a.verify_markdown_round_trip(b"# x\n", rendered, "a.md"))

    def test_a_crlf_source_still_verifies_against_the_lf_page(self) -> None:
        from artefact_sync import render

        entry = Entry(
            id="e", source=PurePosixPath("a.md"),
            destination=PurePosixPath("a/index.html"), title="A",
            collection="c", order=10, replacements={},
        )
        template = string.Template("<html>$block_start$markdown$block_end</html>")
        rendered = render.render_markdown_page(
            entry,
            b"# x\r\n",
            PurePosixPath("vendor/marked.min.js"),
            site_from_dict({"base_url": "https://x.example/artefacts/"}),
            template,
        )
        self.assertIsNone(a.verify_markdown_round_trip(b"# x\r\n", rendered, "a.md"))

    def test_raises_when_the_page_carries_different_markdown(self) -> None:
        rendered = (b'<script type="text/markdown" id="markdown-source">\n'
                    b"# DIFFERENT\n</script>")
        with self.assertRaises(ValidationError):
            a.verify_markdown_round_trip(b"# x\n", rendered, "a.md")

    def test_raises_when_the_page_carries_no_markdown_block(self) -> None:
        with self.assertRaises(ValidationError):
            a.verify_markdown_round_trip(b"# x\n", b"<html></html>", "a.md")


class ApplyTests(unittest.TestCase):
    def test_writes_are_atomic_leaving_no_temp_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "artefacts"
            root.mkdir()
            a.write_atomic(root / "deep/a.txt", b"x")
            self.assertEqual(b"x", (root / "deep/a.txt").read_bytes())
            self.assertEqual([], [p.name for p in root.rglob("*.tmp")])

    def test_refuses_to_write_outside_the_artefacts_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "artefacts"
            root.mkdir()
            with self.assertRaises(ValidationError):
                resolve_within(
                    root,
                    root / "../escape.txt",
                    ValidationError,
                    "destination escapes artefacts directory",
                )

    def test_an_orphan_is_never_unlinked(self) -> None:
        from artefact_sync import plan as p

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "artefacts"
            root.mkdir()
            (root / "redirect.html").write_bytes(b"hand written")
            sync_plan = p.SyncPlan(
                changes=(), notes=(p.Note("orphan", "artefacts/redirect.html", "kept"),),
                blocked=(), desired_files={}, next_manifest=None,
            )
            site = site_from_dict({"base_url": "https://x.example/artefacts/"})
            context = Context(root.parent, root.parent / "source", root, site)
            a.apply_plan(context, sync_plan)
            self.assertTrue((root / "redirect.html").is_file())
