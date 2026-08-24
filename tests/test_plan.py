from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePosixPath

from artefact_sync import cli, manifest as manifest_module, plan as p
from artefact_sync.config import Context, Site
from artefact_sync.errors import ValidationError
from artefact_sync.manifest import Manifest
from tests.helpers import make_repo, make_source_tree


class GroupingTests(unittest.TestCase):
    def _plan(self) -> p.SyncPlan:
        return p.SyncPlan(
            changes=(
                p.Change("add", PurePosixPath("t/c/index.html"), PurePosixPath("t/c.html"),
                         14_540, "https://x.example/artefacts/t/c/", None),
                p.Change("update", PurePosixPath("i/q/index.html"), PurePosixPath("i/q.md"),
                         900, "https://x.example/artefacts/i/q/", "+12 -3"),
                p.Change("delete", PurePosixPath("old.pdf"), None, None,
                         "https://x.example/artefacts/old.pdf", None),
            ),
            notes=(
                p.Note("orphan", "artefacts/redirect.html", "in repo, in no manifest"),
                p.Note("secret", "t/c.html:88", "looks like an API key"),
            ),
            blocked=(p.Blocked("d/flow.svg:42", "script element"),),
            desired_files={}, next_manifest=None,
        )

    def test_groups_by_consequence_not_by_operation(self) -> None:
        text = p.format_plan(self._plan())
        self.assertLess(text.index("NEW PUBLIC URLS"), text.index("CHANGED"))
        self.assertLess(text.index("CHANGED"), text.index("WILL START 404-ING"))
        self.assertLess(text.index("WILL START 404-ING"), text.index("WARNINGS"))

    def test_adds_show_a_full_url_and_a_human_size(self) -> None:
        text = p.format_plan(self._plan())
        self.assertIn("https://x.example/artefacts/t/c/", text)
        self.assertIn("14.2 KB", text)

    def test_deletions_are_described_as_urls_that_will_404(self) -> None:
        self.assertIn("https://x.example/artefacts/old.pdf", p.format_plan(self._plan()))

    def test_orphans_appear_as_warnings_and_never_as_deletions(self) -> None:
        text = p.format_plan(self._plan())
        warnings = text[text.index("WARNINGS"):]
        self.assertIn("redirect.html", warnings)
        self.assertNotIn("redirect.html", text[: text.index("WARNINGS")])

    def test_orphan_is_not_a_deletion_kind(self) -> None:
        self.assertNotIn("orphan", p.DELETION_KINDS)

    def test_a_blocked_file_is_reported_last_and_names_the_line(self) -> None:
        text = p.format_plan(self._plan())
        self.assertIn("BLOCKED", text)
        self.assertIn("d/flow.svg:42", text)

    def test_an_empty_plan_says_so_without_empty_headings(self) -> None:
        text = p.format_plan(
            p.SyncPlan(changes=(), notes=(), blocked=(), desired_files={}, next_manifest=None)
        )
        self.assertNotIn("NEW PUBLIC URLS", text)
        self.assertIn("no changes", text.lower())

    def test_no_emoji_anywhere_in_the_output(self) -> None:
        for char in p.format_plan(self._plan()):
            self.assertLess(ord(char), 0x2190, f"non-ascii-art character {char!r}")


class CatalogueConfigTests(unittest.TestCase):
    def test_plan_rejects_inject_mode_without_a_catalogue_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {})
            site = Site("https://x.example/artefacts/", "", "inject", None)
            context = Context(repo, source, repo / "artefacts", site)
            current = Manifest(1, site, (), (), (), ())
            with self.assertRaises(ValidationError) as caught:
                p.create_sync_plan(context, current)
        self.assertIn("site.catalogue", str(caught.exception))


class OrphanNoteTests(unittest.TestCase):
    """Design invariant 4 promises orphans are never deleted. Do not print it about a deletion."""

    def _synced_repo(self, tmp: Path, files: dict) -> tuple[Path, Path, Path]:
        root = Path(tmp)
        repo = make_repo(root, {"README.md": b"x\n"})
        source = make_source_tree(root, files)
        pointer = root / "pointer.json"
        cli.main(["init", "--pointer", str(pointer),
                  "--repo", str(repo), "--source", str(source)])
        cli.main(["plan", "--pointer", str(pointer)])            # proposes, exits 3
        cli.main(["sync", "--pointer", str(pointer), "--yes"])   # publishes
        return repo, source, pointer

    def _replan(self, pointer: Path) -> p.SyncPlan:
        context = cli.resolve_context(cli.parse_args(["plan", "--pointer", str(pointer)]))
        return p.create_sync_plan(context, manifest_module.load_manifest(context.artefacts_root))

    def test_a_file_this_run_deletes_is_not_also_called_an_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = self._synced_repo(tmp, {"keep.png": b"keep"})
            (source / "keep.png").unlink()
            sync_plan = self._replan(pointer)
        deleted = [change.destination.as_posix() for change in sync_plan.changes
                   if change.kind in p.DELETION_KINDS]
        self.assertEqual(["keep.png"], deleted)
        self.assertEqual(
            [],
            [note for note in sync_plan.notes
             if note.kind == "orphan" and "keep.png" in note.where],
        )

    def test_a_genuinely_unmanaged_file_is_still_warned_about(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, pointer = self._synced_repo(tmp, {"keep.png": b"keep"})
            (repo / "artefacts" / "redirect.html").write_bytes(b"<html></html>\n")
            sync_plan = self._replan(pointer)
        self.assertEqual(
            ["artefacts/redirect.html"],
            [note.where for note in sync_plan.notes if note.kind == "orphan"],
        )
