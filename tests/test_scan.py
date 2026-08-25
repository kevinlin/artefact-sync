from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePosixPath

import scan
from tests.helpers import make_repo, make_source_tree


class WalkTests(unittest.TestCase):
    def test_reports_only_approved_extensions_and_counts_the_rest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), {
                "a/keep.png": b"1", "a/keep.svg": b"<svg/>", "a/skip.psd": b"2",
                "a/skip2.psd": b"3", "a/.DS_Store": b"4",
            })
            inventory = scan.scan_source(source, Path(tmp) / "nowhere")
        self.assertEqual(
            [PurePosixPath("a/keep.png"), PurePosixPath("a/keep.svg")],
            sorted(inventory.approved),
        )
        self.assertIn((".psd", 2), inventory.excluded)

    def test_prunes_the_destination_repo_when_it_sits_inside_the_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), {"a/keep.png": b"1"})
            repo = make_repo(source, {"artefacts/published.png": b"2"})
            inventory = scan.scan_source(source, repo)
        self.assertEqual([PurePosixPath("a/keep.png")], sorted(inventory.approved))

    def test_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), {"real.png": b"1"})
            (source / "link.png").symlink_to(source / "real.png")
            inventory = scan.scan_source(source, Path(tmp) / "nowhere")
        self.assertEqual([PurePosixPath("real.png")], sorted(inventory.approved))


class IgnoreTests(unittest.TestCase):
    def test_a_directory_rule_ignores_the_whole_subtree(self) -> None:
        self.assertTrue(scan.is_ignored(PurePosixPath("talk/prompts/x.md"), ("talk/prompts/",)))

    def test_a_directory_rule_does_not_match_a_sibling_prefix(self) -> None:
        self.assertFalse(scan.is_ignored(PurePosixPath("talk/promptsy.md"), ("talk/prompts/",)))

    def test_a_bare_directory_rule_matches_that_directory_at_any_depth(self) -> None:
        # The prior art matched a "dir/" rule only at the root, which is why manifests
        # written by it carry full prefixes like "fde/prompts/". Carrying such a
        # manifest over and shortening a rule silently widens it. See M4-i.
        self.assertTrue(scan.is_ignored(PurePosixPath("a/b/prompts/x.md"), ("prompts/",)))
        self.assertTrue(scan.is_ignored(PurePosixPath("prompts/x.md"), ("prompts/",)))
        self.assertFalse(scan.is_ignored(PurePosixPath("a/prompts.md"), ("prompts/",)))

    def test_an_exact_rule_matches_only_that_file(self) -> None:
        self.assertTrue(scan.is_ignored(PurePosixPath("a/b.md"), ("a/b.md",)))
        self.assertFalse(scan.is_ignored(PurePosixPath("a/bb.md"), ("a/b.md",)))

    def test_a_glob_rule_matches_at_any_depth(self) -> None:
        self.assertTrue(scan.is_ignored(PurePosixPath("deep/a.local.html"), ("*.local.*",)))
        self.assertTrue(scan.is_ignored(PurePosixPath("a.local.html"), ("*.local.*",)))

    def test_the_dotfile_seed_matches_hidden_files_at_any_depth(self) -> None:
        self.assertTrue(scan.is_ignored(PurePosixPath("deep/.env"), (".*",)))
        self.assertFalse(scan.is_ignored(PurePosixPath("deep/env"), (".*",)))

    def test_rule_counts_are_reported_so_a_dead_rule_is_visible(self) -> None:
        inventory = scan.SourceInventory(
            approved=(PurePosixPath("a.local.html"), PurePosixPath("b.png")), excluded=()
        )
        kept, counts = scan.apply_source_ignores(inventory, ("*.local.*", "never-matches/"))
        self.assertEqual((PurePosixPath("b.png"),), kept.approved)
        self.assertIn(("never-matches/", 0), counts)
