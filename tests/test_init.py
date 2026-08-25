from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cli, manifest
from tests.helpers import make_repo, make_source_tree

ENV = {"PATH": "/usr/bin:/bin:/usr/local/bin"}


class InitTests(unittest.TestCase):
    def _init(self, root: Path) -> tuple[Path, Path, Path]:
        repo = make_repo(root, {"README.md": b"x\n"})
        source = make_source_tree(root, {})
        pointer = root / "pointer.json"
        code = cli.main(["init", "--pointer", str(pointer),
                         "--repo", str(repo), "--source", str(source)])
        self.assertEqual(cli.EXIT_OK, code)
        return repo, source, pointer

    def test_writes_a_pointer_naming_both_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, source, pointer = self._init(Path(tmp))
            body = json.loads(pointer.read_text())
        self.assertEqual(repo.resolve(), Path(body["repo"]).resolve())
        self.assertEqual(source.resolve(), Path(body["source"]).resolve())
        self.assertEqual("direct", body["push"])

    def test_creates_every_control_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, _pointer = self._init(Path(tmp))
            found = {
                relative: (repo / relative).is_file()
                for relative in (
                    "artefacts/manifest.json", "artefacts/page-template.html",
                    "artefacts/index.html", "artefacts/vendor/marked.min.js",
                )
            }
        for relative, exists in found.items():
            self.assertTrue(exists, relative)

    def test_registers_the_vendor_file_so_markdown_can_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, _pointer = self._init(Path(tmp))
            loaded = manifest.load_manifest(repo / "artefacts")
        from render import markdown_vendor_path

        self.assertEqual("vendor/marked.min.js", markdown_vendor_path(loaded).as_posix())

    def test_seeds_ignore_rules_that_actually_match(self) -> None:
        from scan import is_ignored
        from pathlib import PurePosixPath

        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, _pointer = self._init(Path(tmp))
            rules = manifest.load_manifest(repo / "artefacts").ignored_sources
        self.assertTrue(is_ignored(PurePosixPath("talk/prompts/x.md"), rules))
        self.assertTrue(is_ignored(PurePosixPath("deep/notes.local.md"), rules))
        self.assertTrue(is_ignored(PurePosixPath("deep/.env"), rules))

    def test_is_idempotent_and_never_overwrites_an_existing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, source, pointer = self._init(root)
            marker = repo / "artefacts" / "manifest.json"
            before = marker.read_bytes()
            marker.write_bytes(before.replace(b'"entries": []', b'"entries": []'))
            code = cli.main(["init", "--pointer", str(pointer),
                            "--repo", str(repo), "--source", str(source)])
            self.assertEqual(cli.EXIT_OK, code)
            self.assertEqual(before, marker.read_bytes())


class InitVerificationTests(unittest.TestCase):
    def _run(self, status: int) -> tuple[int, str, mock.Mock]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/someone/notes.git"],
                cwd=repo, env=ENV, check=True,
            )
            source = make_source_tree(root, {})
            output = io.StringIO()
            with mock.patch.object(cli.provider, "fetch", return_value=status) as fetch:
                with contextlib.redirect_stdout(output):
                    code = cli.main(["init", "--pointer", str(root / "pointer.json"),
                                     "--repo", str(repo), "--source", str(source)])
        return code, output.getvalue(), fetch

    def test_reports_a_reachable_pages_url(self) -> None:
        code, output, fetch = self._run(200)
        self.assertEqual(cli.EXIT_OK, code)
        fetch.assert_called_once_with("https://someone.github.io/notes/artefacts/")
        self.assertIn("verified https://someone.github.io/notes/artefacts/", output)

    def test_warns_but_still_succeeds_when_the_url_is_not_live(self) -> None:
        code, output, _fetch = self._run(404)
        self.assertEqual(cli.EXIT_OK, code)
        self.assertIn("returned 404", output)
        self.assertIn("site.base_url", output)

    def test_warns_when_the_request_never_completes(self) -> None:
        code, output, _fetch = self._run(0)
        self.assertEqual(cli.EXIT_OK, code)
        self.assertIn("did not respond", output)

    def test_never_fetches_without_a_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {})
            with mock.patch.object(cli.provider, "fetch") as fetch:
                with contextlib.redirect_stdout(io.StringIO()):
                    cli.main(["init", "--pointer", str(root / "pointer.json"),
                              "--repo", str(repo), "--source", str(source)])
        fetch.assert_not_called()
