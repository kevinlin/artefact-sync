from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from artefact_sync import cli, manifest
from artefact_sync.config import site_from_dict
from tests.helpers import make_repo, make_source_tree


def seed_manifest(repo: Path) -> None:
    body = manifest.Manifest(
        version=1,
        site=site_from_dict({"base_url": "https://x.example/artefacts/"}),
        protected_files=(), ignored_sources=(), collections=(), entries=(),
    )
    artefacts = repo / "artefacts"
    artefacts.mkdir(exist_ok=True)
    (artefacts / "manifest.json").write_text(manifest.manifest_to_json(body), encoding="utf-8")


class ContextResolutionTests(unittest.TestCase):
    def test_works_from_any_cwd_using_the_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            seed_manifest(repo)
            source = make_source_tree(root, {"a.png": b"1"})
            pointer = root / "pointer.json"
            pointer.write_text(json.dumps(
                {"repo": str(repo), "source": str(source), "push": "direct"}))
            elsewhere = root / "elsewhere"
            elsewhere.mkdir()
            previous = os.getcwd()
            os.chdir(elsewhere)
            try:
                context = cli.resolve_context(cli.parse_args(
                    ["plan", "--pointer", str(pointer)]))
            finally:
                os.chdir(previous)
        self.assertEqual(repo.resolve(), context.repo_root.resolve())

    def test_explicit_flags_beat_the_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            seed_manifest(repo)
            other = root / "other"
            (other / "artefacts").mkdir(parents=True)
            seed_manifest(other)
            source = make_source_tree(root, {"a.png": b"1"})
            pointer = root / "pointer.json"
            pointer.write_text(json.dumps(
                {"repo": str(repo), "source": str(source), "push": "direct"}))
            context = cli.resolve_context(cli.parse_args(
                ["plan", "--pointer", str(pointer), "--repo", str(other)]))
        self.assertEqual(other.resolve(), context.repo_root.resolve())


class ExitCodeTests(unittest.TestCase):
    def test_a_missing_pointer_exits_1_and_names_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                code = cli.main(["plan", "--pointer", str(Path(tmp) / "absent.json")])
        self.assertEqual(cli.EXIT_ERROR, code)
        self.assertIn("init", buffer.getvalue())

    def test_unknown_command_exits_nonzero(self) -> None:
        with self.assertRaises(SystemExit):
            cli.parse_args(["nope"])

    def test_no_command_prints_usage(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer), contextlib.redirect_stdout(buffer):
            code = cli.main([])
        self.assertEqual(cli.EXIT_ERROR, code)
        self.assertIn("init", buffer.getvalue())
