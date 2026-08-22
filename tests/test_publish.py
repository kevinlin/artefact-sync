from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from artefact_sync import config, manifest, publish
from artefact_sync.config import site_from_dict
from artefact_sync.errors import PublishError
from tests.helpers import RecordingRunner, make_repo, make_source_tree

BASE_URL = "https://someone.github.io/notes/artefacts/"


def make_context(root: Path, push: str = "direct") -> config.Context:
    repo = make_repo(root, {"README.md": b"x\n"})
    source = make_source_tree(root, {})
    artefacts = repo / "artefacts"
    artefacts.mkdir(exist_ok=True)
    body = manifest.Manifest(
        version=1, site=site_from_dict({"base_url": BASE_URL}),
        protected_files=(), ignored_sources=(), collections=(), entries=(),
    )
    (artefacts / manifest.MANIFEST_NAME).write_text(
        manifest.manifest_to_json(body), encoding="utf-8"
    )
    return config.Context(repo, source, artefacts, body.site, push)


class PreflightTests(unittest.TestCase):
    def preflight(self, overrides: dict | None = None, push: str = "direct") -> str:
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp), push)
            self.runner = RecordingRunner(overrides)
            return publish.preflight(context, self.runner)

    def test_a_clean_tree_on_the_default_branch_passes(self) -> None:
        self.assertEqual("main", self.preflight())

    def test_reads_the_default_branch_from_origin_head(self) -> None:
        self.assertEqual("trunk", self.preflight({
            "git rev-parse --abbrev-ref origin/HEAD": ("origin/trunk\n", "", 0),
            "git branch --show-current": ("trunk\n", "", 0),
        }))

    def test_falls_back_to_main_when_origin_head_is_unset(self) -> None:
        self.assertEqual("main", self.preflight({
            "git rev-parse --abbrev-ref origin/HEAD": ("", "no upstream\n", 128),
        }))

    def test_rejects_a_missing_git(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({"git --version": ("", "not found\n", 127)})
        self.assertIn("git is not available", str(caught.exception))

    def test_rejects_a_missing_github_cli(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({"gh --version": ("", "not found\n", 127)})
        self.assertIn("gh", str(caught.exception))

    def test_rejects_an_unauthenticated_github_cli(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({"gh auth status": ("", "not logged in\n", 1)})
        self.assertIn("gh auth login", str(caught.exception))

    def test_skips_the_github_checks_for_another_host(self) -> None:
        self.preflight({
            "git remote get-url origin": ("git@gitlab.example:someone/notes.git\n", "", 0),
        })
        self.assertEqual([], self.runner.ran("gh "))

    def test_rejects_a_repository_with_no_origin(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({"git remote get-url origin": ("", "no such remote\n", 2)})
        self.assertIn("origin", str(caught.exception))

    def test_rejects_tracked_changes_outside_artefacts(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({
                "git status --porcelain -z": (" M index.html\0 M artefacts/manifest.json\0", "", 0),
            })
        self.assertIn("index.html", str(caught.exception))
        self.assertNotIn("artefacts/manifest.json", str(caught.exception))

    def test_accepts_a_dirty_artefacts_tree(self) -> None:
        self.assertEqual("main", self.preflight({
            "git status --porcelain -z": (
                " M artefacts/manifest.json\0?? artefacts/talk/new/index.html\0", "", 0
            ),
        }))

    def test_ignores_untracked_files_elsewhere(self) -> None:
        self.assertEqual("main", self.preflight({
            "git status --porcelain -z": ("?? scratch.md\0?? notes/\0", "", 0),
        }))

    def test_reads_a_rename_at_its_new_path(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({
                "git status --porcelain -z": ("R  moved.html\0artefacts/old.html\0", "", 0),
            })
        self.assertIn("moved.html", str(caught.exception))

    def test_rejects_publishing_from_another_branch(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({"git branch --show-current": ("spike\n", "", 0)})
        self.assertIn("switch main", str(caught.exception))

    def test_rejects_a_diverged_branch_and_names_the_recovery(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({"git rev-list --left-right --count": ("1\t2\n", "", 0)})
        self.assertIn("diverged", str(caught.exception))
        self.assertIn("pull --ff-only", str(caught.exception))


class CommitAndPushTests(unittest.TestCase):
    def run_it(self, branch: str = "main", overrides: dict | None = None) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            self.runner = RecordingRunner(overrides)
            return publish.commit_and_push(context, branch, "main", self.runner)

    def test_returns_the_new_commit(self) -> None:
        self.assertEqual("abc123def4567890", self.run_it())

    def test_direct_mode_never_creates_a_branch(self) -> None:
        self.run_it()
        self.assertEqual([], self.runner.ran("git switch"))
        self.assertEqual([["git", "push", "origin", "main"]], self.runner.ran("git push"))

    def test_branch_mode_creates_the_branch_before_staging(self) -> None:
        self.run_it("artefact-sync/20260823-120000")
        self.assertLess(
            self.runner.index("git switch -c"), self.runner.index("git add"),
        )
        self.assertEqual(
            [["git", "push", "origin", "artefact-sync/20260823-120000"]],
            self.runner.ran("git push"),
        )

    def test_stages_the_directory_rather_than_named_paths(self) -> None:
        self.run_it()
        self.assertEqual(
            [["git", "add", "--all", "--", "artefacts"]], self.runner.ran("git add")
        )

    def test_never_force_pushes(self) -> None:
        self.run_it()
        for call in self.runner.calls:
            self.assertNotIn("--force", call)
            self.assertNotIn("-f", call)

    def test_a_failed_push_names_the_local_commit_in_its_recovery(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.run_it(overrides={"git push origin": ("", "network is down\n", 128)})
        message = str(caught.exception)
        self.assertIn("abc123def456", message)
        self.assertIn("Nothing is live", message)
        self.assertIn("git -C", message)
        self.assertIn("push origin main", message)

    def test_a_failed_commit_stops_before_any_push(self) -> None:
        with self.assertRaises(PublishError):
            self.run_it(overrides={"git commit -m": ("", "nothing to commit\n", 1)})
        self.assertEqual([], self.runner.ran("git push"))
