from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from artefact_sync import cli, manifest
from tests.helpers import make_repo, make_source_tree

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
        from artefact_sync.render import markdown_vendor_path

        self.assertEqual("vendor/marked.min.js", markdown_vendor_path(loaded).as_posix())

    def test_seeds_ignore_rules_that_actually_match(self) -> None:
        from artefact_sync.scan import is_ignored
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
