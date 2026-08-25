from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path, PurePosixPath
from unittest import mock

import cli, config, manifest, plan as plan_module, publish
from config import site_from_dict
from errors import PublishError, ValidationError
from tests.helpers import RecordingFetcher, RecordingRunner, make_repo, make_source_tree

BASE_URL = "https://someone.github.io/notes/artefacts/"
PAGE = b"<html><head></head><body><h1>Cost model</h1></body></html>\n"


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


def make_publishing_world(root: Path, push: str = "direct", extra: dict | None = None):
    """init, then one plan run, so the manifest holds a proposal and a file is waiting."""
    repo = make_repo(root, {"README.md": b"x\n"})
    source = make_source_tree(root, dict({"talk/cost-model.html": PAGE}, **(extra or {})))
    pointer = root / "pointer.json"
    with contextlib.redirect_stdout(io.StringIO()):
        cli.main(["init", "--pointer", str(pointer),
                  "--repo", str(repo), "--source", str(source)])
        cli.main(["plan", "--pointer", str(pointer)])
    body = manifest.load_manifest(repo / "artefacts")
    context = config.Context(repo.resolve(), source.resolve(),
                             repo.resolve() / "artefacts", body.site, push)
    return context, body, pointer


class _SnapshotRunner(RecordingRunner):
    """Records whether a published file was on disk by the time staging ran."""

    def __init__(self, target: Path, overrides: dict | None = None) -> None:
        super().__init__(overrides)
        self.target = target
        self.existed_at_add = None

    def __call__(self, args, cwd):
        if args[:2] == ["git", "add"]:
            self.existed_at_add = self.target.is_file()
        return super().__call__(args, cwd)


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


class PublicUrlTests(unittest.TestCase):
    def _manifest(self, **overrides) -> manifest.Manifest:
        entries = (
            manifest.Entry(id="note", source=PurePosixPath("note.md"),
                           destination=PurePosixPath("incident/note/index.html"),
                           title="Note", collection="c", order=1),
            manifest.Entry(id="curve", source=PurePosixPath("curve.png"),
                           destination=PurePosixPath("talk/curve.png"),
                           title="Curve", collection="c", order=2),
        )
        body = {"version": 1, "site": site_from_dict({"base_url": BASE_URL}),
                "protected_files": (PurePosixPath("vendor/marked.min.js"),),
                "ignored_sources": (), "collections": (), "entries": entries}
        body.update(overrides)
        return manifest.Manifest(**body)

    def test_covers_the_catalogue_every_entry_and_every_protected_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            urls = publish.public_urls(context, self._manifest())
        self.assertEqual(
            (BASE_URL,
             BASE_URL + "incident/note/",
             BASE_URL + "talk/curve.png",
             BASE_URL + "vendor/marked.min.js"),
            urls,
        )

    def test_adds_the_host_page_in_inject_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            site = site_from_dict(
                {"base_url": BASE_URL, "catalogue": {"mode": "inject", "page": "gallery.html"}}
            )
            context = config.Context(context.repo_root, context.source_root,
                                     context.artefacts_root, site, "direct")
            urls = publish.public_urls(context, self._manifest())
        self.assertIn(BASE_URL + "gallery.html", urls)


class VerifyPublicUrlsTests(unittest.TestCase):
    def test_fetches_every_url(self) -> None:
        fetcher = RecordingFetcher()
        publish.verify_public_urls((BASE_URL, BASE_URL + "a.png"), fetcher)
        self.assertEqual([BASE_URL, BASE_URL + "a.png"], fetcher.urls)

    def test_a_non_200_names_the_url_the_code_and_the_absence_of_rollback(self) -> None:
        fetcher = RecordingFetcher(overrides={BASE_URL + "a.png": 404})
        with self.assertRaises(PublishError) as caught:
            publish.verify_public_urls((BASE_URL, BASE_URL + "a.png"), fetcher)
        message = str(caught.exception)
        self.assertIn("a.png", message)
        self.assertIn("404", message)
        self.assertIn("was not rolled back", message)

    def test_a_dead_host_reports_no_response(self) -> None:
        with self.assertRaises(PublishError) as caught:
            publish.verify_public_urls((BASE_URL,), RecordingFetcher(status=0))
        self.assertIn("no response", str(caught.exception))


class PublishTests(unittest.TestCase):
    def run_publish(self, context, current, runner=None, fetcher=None,
                    answer: str = "yes", overrides: dict | None = None):
        self.runner = runner or RecordingRunner(overrides)
        self.fetcher = fetcher or RecordingFetcher()
        self.prompt = []
        self.output = io.StringIO()
        with contextlib.redirect_stdout(self.output):
            return publish.publish(
                context, current, self.runner, self.fetcher,
                confirm=lambda text: (self.prompt.append(text), answer)[1],
                now=lambda: datetime(2026, 8, 23, 12, 0, 0),
                sleeper=lambda _seconds: None,
            )

    def test_publishes_applies_validates_commits_pushes_waits_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            page = context.artefacts_root / "talk" / "cost-model" / "index.html"
            runner = _SnapshotRunner(page)
            result = self.run_publish(context, current, runner=runner)
        self.assertTrue(runner.existed_at_add, "apply must run before staging")
        self.assertLess(runner.index("git push"), runner.index("gh api"))
        self.assertEqual("abc123def4567890", result.commit)
        self.assertEqual("main", result.branch)
        self.assertTrue(result.live)
        self.assertIn(context.site.base_url, self.fetcher.urls)
        self.assertEqual(result.verified_url_count, len(self.fetcher.urls))

    def test_verification_runs_after_the_build_wait(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            runner = RecordingRunner()
            commands_before_first_fetch = []

            class _CountingFetcher(RecordingFetcher):
                def __call__(self, url, timeout=10.0):
                    commands_before_first_fetch.append(len(runner.calls))
                    return super().__call__(url, timeout)

            self.run_publish(context, current, runner=runner, fetcher=_CountingFetcher())
        self.assertTrue(commands_before_first_fetch)
        self.assertGreater(commands_before_first_fetch[0], runner.index("gh api"))

    def test_a_declined_confirmation_applies_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            page = context.artefacts_root / "talk" / "cost-model" / "index.html"
            self.assertIsNone(self.run_publish(context, current, answer="no"))
            self.assertFalse(page.is_file())
        self.assertEqual([], self.runner.ran("git commit"))
        self.assertIn("cancelled", self.output.getvalue())

    def test_the_confirmation_states_the_urls_and_the_irreversibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            self.run_publish(context, current, answer="no")
        text = self.prompt[0]
        self.assertIn("talk/cost-model/", text)
        self.assertIn("irreversible", text)
        self.assertIn("Type yes to continue", text)

    def test_no_changes_verifies_the_urls_and_commits_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, pointer = make_publishing_world(Path(tmp))
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(["sync", "--pointer", str(pointer), "--yes"])
            current = manifest.load_manifest(context.artefacts_root)
            self.assertIsNone(self.run_publish(context, current))
        self.assertEqual([], self.runner.ran("git commit"))
        self.assertIn("nothing to publish", self.output.getvalue())
        self.assertIn(context.site.base_url, self.fetcher.urls)

    def test_a_blocked_plan_raises_before_anything_is_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(
                Path(tmp), extra={"diagrams/bad.svg": b"<svg>\n<script/>\n</svg>\n"}
            )
            with self.assertRaises(publish.BlockedPlan) as caught:
                self.run_publish(context, current)
        self.assertEqual([], self.runner.ran("git commit"))
        self.assertTrue(caught.exception.plan.blocked)

    def test_protected_branch_mode_pushes_a_branch_and_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp), push="branch")
            result = self.run_publish(context, current)
        self.assertEqual("artefact-sync/20260823-120000", result.branch)
        self.assertFalse(result.live)
        self.assertEqual(0, result.verified_url_count)
        self.assertEqual([], self.runner.ran("gh api"))
        self.assertEqual([], self.fetcher.urls)
        self.assertIn("compare/main...artefact-sync/20260823-120000", self.output.getvalue())

    def test_another_host_skips_the_build_wait_and_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            result = self.run_publish(context, current, overrides={
                "git remote get-url origin": ("git@gitlab.example:someone/notes.git\n", "", 0),
            })
        self.assertEqual([], self.runner.ran("gh "))
        self.assertEqual(0, result.verified_url_count)
        self.assertIn("no build API", self.output.getvalue())

    def test_a_failed_validate_stops_before_the_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            with mock.patch.object(
                publish.validate_module, "validate_repository",
                side_effect=ValidationError("catalogue link missing"),
            ):
                with self.assertRaises(PublishError) as caught:
                    self.run_publish(context, current)
        self.assertEqual([], self.runner.ran("git commit"))
        self.assertIn("catalogue link missing", str(caught.exception))
        self.assertIn("nothing was committed", str(caught.exception))

    def test_a_failed_apply_names_sync_as_the_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            with mock.patch.object(
                publish.apply_module, "apply_plan",
                side_effect=ValidationError("applied file differs from plan"),
            ):
                with self.assertRaises(PublishError) as caught:
                    self.run_publish(context, current)
        self.assertIn("artefact-sync sync", str(caught.exception))

    def test_never_force_pushes_or_resets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            self.run_publish(context, current)
        for call in self.runner.calls:
            joined = " ".join(call)
            for banned in ("--force", " -f", "reset --hard", "revert"):
                self.assertNotIn(banned, joined)


class PublishCommandTests(unittest.TestCase):
    def test_runs_the_self_check_before_publishing(self) -> None:
        order = []
        with tempfile.TemporaryDirectory() as tmp:
            _context, _current, pointer = make_publishing_world(Path(tmp))
            with mock.patch.object(cli.selfcheck, "run_self_check",
                                   side_effect=lambda *a: order.append("selfcheck")):
                with mock.patch.object(cli.publish, "publish",
                                       side_effect=lambda *a, **k: order.append("publish")):
                    with contextlib.redirect_stdout(io.StringIO()):
                        code = cli.main(["publish", "--pointer", str(pointer)])
        self.assertEqual(cli.EXIT_OK, code)
        self.assertEqual(["selfcheck", "publish"], order)

    def test_a_blocked_plan_exits_3_and_writes_the_proposal(self) -> None:
        # publish.publish is patched rather than driven: its `runner` default binds at
        # definition time, so patching provider.subprocess_runner afterwards would not
        # reach it, and the real runner would fail preflight on the fixture's absent origin.
        with tempfile.TemporaryDirectory() as tmp:
            context, _current, pointer = make_publishing_world(Path(tmp))
            source = Path(json.loads(pointer.read_text())["source"])
            (source / "curve.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            reloaded = manifest.load_manifest(context.artefacts_root)
            blocked = plan_module.create_sync_plan(context, reloaded)
            self.assertTrue(blocked.blocked)
            with mock.patch.object(cli.selfcheck, "run_self_check"):
                with mock.patch.object(cli.publish, "publish",
                                       side_effect=publish.BlockedPlan(blocked)):
                    with contextlib.redirect_stdout(io.StringIO()):
                        with contextlib.redirect_stderr(io.StringIO()):
                            code = cli.main(["publish", "--pointer", str(pointer)])
            body = json.loads(
                (context.artefacts_root / manifest.MANIFEST_NAME).read_text(encoding="utf-8")
            )
        self.assertEqual(cli.EXIT_BLOCKED, code)
        self.assertIn("curve.png", {entry["source"] for entry in body["entries"]})

    def test_reports_the_commit_and_the_verified_count(self) -> None:
        result = publish.PublishResult("main", "abc123def4567890", True,
                                       "https://x.example/artefacts/", 4)
        with tempfile.TemporaryDirectory() as tmp:
            _context, _current, pointer = make_publishing_world(Path(tmp))
            output = io.StringIO()
            with mock.patch.object(cli.selfcheck, "run_self_check"):
                with mock.patch.object(cli.publish, "publish", return_value=result):
                    with contextlib.redirect_stdout(output):
                        code = cli.main(["publish", "--pointer", str(pointer)])
        self.assertEqual(cli.EXIT_OK, code)
        self.assertIn("abc123def456", output.getvalue())
        self.assertIn("verified 4", output.getvalue())
