from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path, PurePosixPath

import cli, manifest as manifest_module, plan as p
from config import Context, Site
from errors import ValidationError
from manifest import Manifest
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
            site = Site("https://x.example/artefacts/", "", "", "inject", None)
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


class DateStampTests(unittest.TestCase):
    """A republished artefact is redated from its source; an untouched one keeps its date."""

    def _synced(self, tmp: str) -> tuple[Path, Path]:
        root = Path(tmp)
        repo = make_repo(root, {"README.md": b"x\n"})
        source = make_source_tree(root, {"note.md": b"# note\n", "still.md": b"# still\n"})
        pointer = root / "pointer.json"
        cli.main(["init", "--pointer", str(pointer),
                  "--repo", str(repo), "--source", str(source)])
        cli.main(["plan", "--pointer", str(pointer)])
        cli.main(["sync", "--pointer", str(pointer), "--yes"])
        return source, pointer

    def test_an_updated_artefact_is_redated_and_an_untouched_one_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source, pointer = self._synced(tmp)
            context = cli.resolve_context(cli.parse_args(["plan", "--pointer", str(pointer)]))
            before = {entry.id: entry.date
                      for entry in manifest_module.load_manifest(context.artefacts_root).entries}
            changed = source / "note.md"
            changed.write_bytes(b"# note, revised\n")
            os.utime(changed, (1_800_000_000, 1_800_000_000))
            sync_plan = p.create_sync_plan(
                context, manifest_module.load_manifest(context.artefacts_root))
        dates = {entry.id: entry.date for entry in sync_plan.next_manifest.entries}
        expected = date.fromtimestamp(1_800_000_000).isoformat()
        self.assertEqual(expected, dates["note"])
        self.assertNotEqual(before["note"], dates["note"])
        self.assertEqual(before["still"], dates["still"])


class ExcludedBlockTests(unittest.TestCase):
    def test_unsupported_files_are_summarised(self) -> None:
        text = p.format_plan(
            p.SyncPlan(
                changes=(), notes=(), blocked=(), desired_files={}, next_manifest=None,
                excluded=((".psd", 1), (".mp4", 2)),
            )
        )
        self.assertIn("EXCLUDED (3)", text)
        self.assertIn(".psd", text)
        self.assertIn("1 file, unsupported type", text)
        self.assertIn("2 files, unsupported type", text)

    def test_ignored_files_are_summarised(self) -> None:
        text = p.format_plan(
            p.SyncPlan(
                changes=(), notes=(), blocked=(), desired_files={}, next_manifest=None,
                ignored=(("drafts/", 3),),
            )
        )
        self.assertIn("EXCLUDED (3)", text)
        self.assertIn("drafts/", text)
        self.assertIn("3 files, matched an ignored source rule", text)

    def test_excluded_heading_totals_all_reasons(self) -> None:
        text = p.format_plan(
            p.SyncPlan(
                changes=(), notes=(), blocked=(), desired_files={}, next_manifest=None,
                excluded=((".psd", 1),), ignored=(("drafts/", 3),),
            )
        )
        self.assertIn("EXCLUDED (4)", text)

    def test_nothing_excluded_prints_no_heading(self) -> None:
        text = p.format_plan(
            p.SyncPlan(changes=(), notes=(), blocked=(), desired_files={}, next_manifest=None)
        )
        self.assertNotIn("EXCLUDED", text)

    def test_excluded_sits_between_the_change_groups_and_the_warnings(self) -> None:
        text = p.format_plan(
            p.SyncPlan(
                changes=(p.Change("delete", PurePosixPath("old.pdf"), None, None,
                                  "https://x.example/artefacts/old.pdf", None),),
                notes=(p.Note("orphan", "artefacts/redirect.html", "kept"),),
                blocked=(), desired_files={}, next_manifest=None,
                excluded=((".psd", 1),), ignored=(),
            )
        )
        self.assertLess(text.index("WILL START 404-ING"), text.index("EXCLUDED"))
        self.assertLess(text.index("EXCLUDED"), text.index("WARNINGS"))

    def test_a_real_scan_reports_its_own_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {
                "keep.png": b"1", "notes.psd": b"binary", "drafts/wip.md": b"# wip\n",
            })
            pointer = root / "pointer.json"
            cli.main(["init", "--pointer", str(pointer),
                      "--repo", str(repo), "--source", str(source)])
            context = cli.resolve_context(cli.parse_args(["plan", "--pointer", str(pointer)]))
            sync_plan = p.create_sync_plan(
                context, manifest_module.load_manifest(context.artefacts_root))
        self.assertIn((".psd", 1), sync_plan.excluded)
        self.assertIn(("drafts/", 1), sync_plan.ignored)
        self.assertNotIn(("*.local.*", 0), sync_plan.ignored)


class WarningOrderTests(unittest.TestCase):
    def _format(self) -> str:
        return p.format_plan(
            p.SyncPlan(
                changes=(),
                notes=(
                    p.Note("secret", "z.md:1", "looks like an API key"),
                    p.Note("orphan", "artefacts/b.html", "in repo, in no manifest, left alone"),
                    p.Note("external", "a.html:9", "loads https://unpkg.example/x.js at runtime"),
                    p.Note("orphan", "artefacts/a.html", "in repo, in no manifest, left alone"),
                ),
                blocked=(), desired_files={}, next_manifest=None,
            )
        )

    def test_warnings_are_grouped_by_kind(self) -> None:
        text = self._format()
        rows = [line.split()[0] for line in text.splitlines() if line.startswith("  ")]
        self.assertEqual(["external", "orphan", "orphan", "secret"], rows)

    def test_warnings_are_ordered_within_a_kind(self) -> None:
        text = self._format()
        self.assertLess(text.index("artefacts/a.html"), text.index("artefacts/b.html"))
