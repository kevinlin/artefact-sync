from __future__ import annotations

import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from artefact_sync import provider
from artefact_sync.errors import PublishError
from tests.helpers import RecordingRunner, make_repo

ENV = {"PATH": "/usr/bin:/bin:/usr/local/bin"}


class BaseUrlTests(unittest.TestCase):
    def test_maps_recognised_remotes_to_an_artefacts_base_url(self) -> None:
        cases = {
            "git@github.com:someone/someone.github.io.git": "https://someone.github.io/artefacts/",
            "https://github.com/someone/someone.github.io": "https://someone.github.io/artefacts/",
            "git@github.com:someone/notes.git": "https://someone.github.io/notes/artefacts/",
            "https://github.com/someone/notes.git": "https://someone.github.io/notes/artefacts/",
            "https://github.com/someone/notes/": "https://someone.github.io/notes/artefacts/",
            "git@gitlab.com:someone/notes.git": None,
            "": None,
        }
        for remote, expected in cases.items():
            with self.subTest(remote=remote):
                self.assertEqual(expected, provider.base_url_from_remote(remote))

    def test_recognises_github_remotes_only(self) -> None:
        self.assertTrue(provider.is_github("git@github.com:someone/notes.git"))
        self.assertTrue(provider.is_github("https://github.com/someone/notes"))
        self.assertFalse(provider.is_github("git@gitlab.com:someone/notes.git"))
        self.assertFalse(provider.is_github(None))


class DeriveBaseUrlTests(unittest.TestCase):
    def _repo_with_remote(self, tmp: str, remote: str) -> Path:
        repo = make_repo(Path(tmp), {"README.md": b"x\n"})
        subprocess.run(["git", "remote", "add", "origin", remote], cwd=repo, env=ENV, check=True)
        return repo

    def test_user_pages_repo_keeps_the_artefacts_segment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo_with_remote(tmp, "git@github.com:someone/someone.github.io.git")
            self.assertEqual("https://someone.github.io/artefacts/",
                             provider.derive_base_url(repo))

    def test_project_pages_repo_keeps_both_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo_with_remote(tmp, "https://github.com/someone/notes.git")
            self.assertEqual("https://someone.github.io/notes/artefacts/",
                             provider.derive_base_url(repo))

    def test_returns_none_without_a_recognised_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp), {"README.md": b"x\n"})
            self.assertIsNone(provider.derive_base_url(repo))


class RunCheckedTests(unittest.TestCase):
    def test_raises_a_publish_error_carrying_stderr(self) -> None:
        def runner(args, cwd):
            del args, cwd
            return provider.CommandResult("", "fatal: nope\n", 128)

        with self.assertRaises(PublishError) as caught:
            provider.run_checked(runner, ["git", "push"], Path("."), "cannot push")
        self.assertIn("cannot push", str(caught.exception))
        self.assertIn("fatal: nope", str(caught.exception))

    def test_returns_stdout_on_success(self) -> None:
        def runner(args, cwd):
            del args, cwd
            return provider.CommandResult("ok\n", "", 0)

        self.assertEqual("ok\n", provider.run_checked(runner, ["git", "x"], Path("."), "no"))


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200 if self.path == "/ok" else 404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args) -> None:
        del args


class FetchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def test_returns_the_http_status(self) -> None:
        self.assertEqual(200, provider.fetch(self.base + "/ok"))
        self.assertEqual(404, provider.fetch(self.base + "/missing"))

    def test_returns_zero_when_the_request_never_completes(self) -> None:
        self.assertEqual(0, provider.fetch("http://127.0.0.1:1/ok", timeout=0.5))

    def test_refuses_a_non_http_scheme(self) -> None:
        self.assertEqual(0, provider.fetch("file:///etc/passwd"))


class BuildWaitTests(unittest.TestCase):
    def wait(self, overrides: dict | None = None, commit: str = "abc123def4567890") -> None:
        self.runner = RecordingRunner(overrides)
        self.slept = []
        provider.wait_for_build(
            Path("."), "someone/notes", commit, self.runner, self.slept.append
        )

    def test_returns_once_the_build_reports_this_commit_built(self) -> None:
        self.wait()
        self.assertEqual([], self.slept)

    def test_reports_the_pages_error_for_this_commit(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.wait({"gh api repos/someone/notes/pages/builds/latest": (
                '{"status": "errored", "commit": "abc123def4567890",'
                ' "error": {"message": "symlink not allowed"}}\n', "", 0)})
        self.assertIn("symlink not allowed", str(caught.exception))

    def test_keeps_polling_past_an_error_on_an_older_commit(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.wait({"gh api repos/someone/notes/pages/builds/latest": (
                '{"status": "errored", "commit": "0000000000000000",'
                ' "error": {"message": "old failure"}}\n', "", 0)})
        self.assertNotIn("old failure", str(caught.exception))
        self.assertEqual(provider.BUILD_POLL_ATTEMPTS, len(self.slept))

    def test_times_out_and_names_the_recovery(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.wait({"gh api repos/someone/notes/pages/builds/latest": (
                '{"status": "building", "commit": "abc123def4567890"}\n', "", 0)})
        message = str(caught.exception)
        self.assertIn("did not deploy", message)
        self.assertIn("artefact-sync publish", message)

    def test_rejects_an_unparseable_payload(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.wait({"gh api repos/someone/notes/pages/builds/latest": ("not json\n", "", 0)})
        self.assertIn("cannot parse", str(caught.exception))


class RepositoryNameTests(unittest.TestCase):
    def test_reads_name_with_owner(self) -> None:
        self.assertEqual(
            "someone/notes", provider.repository_name(Path("."), RecordingRunner())
        )

    def test_rejects_an_unparseable_payload(self) -> None:
        runner = RecordingRunner({"gh repo view --json nameWithOwner": ("{}\n", "", 0)})
        with self.assertRaises(PublishError):
            provider.repository_name(Path("."), runner)
