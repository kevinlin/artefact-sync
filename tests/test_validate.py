from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from artefact_sync import cli
from tests.helpers import make_repo, make_source_tree


def seeded(root: Path) -> tuple[Path, Path, Path]:
    repo = make_repo(root, {"README.md": b"x\n"})
    source = make_source_tree(root, {})
    pointer = root / "pointer.json"
    cli.main(["init", "--pointer", str(pointer), "--repo", str(repo), "--source", str(source)])
    return repo, source, pointer


class ValidateTests(unittest.TestCase):
    def test_a_freshly_initialised_repo_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, _source, pointer = seeded(Path(tmp))
            self.assertEqual(cli.EXIT_OK, cli.main(["validate", "--pointer", str(pointer)]))

    def test_an_orphan_warns_but_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, pointer = seeded(Path(tmp))
            (repo / "artefacts" / "redirect.html").write_bytes(b"<html>hand written</html>")
            self.assertEqual(cli.EXIT_OK, cli.main(["validate", "--pointer", str(pointer)]))

    def test_a_missing_managed_file_does_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, source, pointer = seeded(Path(tmp))
            (source / "a.png").write_bytes(b"1")
            self.assertEqual(cli.EXIT_BLOCKED, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            next(iter((repo / "artefacts").glob("a*.png"))).unlink()
            self.assertEqual(cli.EXIT_ERROR, cli.main(["validate", "--pointer", str(pointer)]))

    def test_a_missing_protected_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, pointer = seeded(Path(tmp))
            (repo / "artefacts" / "vendor" / "marked.min.js").unlink()
            self.assertEqual(cli.EXIT_ERROR, cli.main(["validate", "--pointer", str(pointer)]))

    def test_a_missing_injected_catalogue_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, pointer = seeded(Path(tmp))
            manifest_path = repo / "artefacts" / "manifest.json"
            body = json.loads(manifest_path.read_text(encoding="utf-8"))
            body["site"]["catalogue"] = {"mode": "inject", "page": "custom.html"}
            manifest_path.write_text(json.dumps(body), encoding="utf-8")
            self.assertEqual(cli.EXIT_ERROR, cli.main(["validate", "--pointer", str(pointer)]))


class SyncTests(unittest.TestCase):
    def test_an_unlisted_approved_source_blocks_with_exit_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = seeded(Path(tmp))
            (source / "new.png").write_bytes(b"1")
            self.assertEqual(cli.EXIT_BLOCKED, cli.main(["plan", "--pointer", str(pointer)]))

    def test_an_unsupported_extension_does_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = seeded(Path(tmp))
            (source / "notes.psd").write_bytes(b"1")
            self.assertEqual(cli.EXIT_OK, cli.main(["plan", "--pointer", str(pointer)]))

    def test_an_ignored_source_does_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = seeded(Path(tmp))
            (source / "drafts").mkdir()
            (source / "drafts" / "wip.md").write_bytes(b"# wip\n")
            self.assertEqual(cli.EXIT_OK, cli.main(["plan", "--pointer", str(pointer)]))

    def test_sync_is_convergent_on_a_second_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, source, pointer = seeded(Path(tmp))
            (source / "a.png").write_bytes(b"1")
            self.assertEqual(cli.EXIT_BLOCKED, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            before = sorted(p.name for p in (repo / "artefacts").rglob("*") if p.is_file())
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            after = sorted(p.name for p in (repo / "artefacts").rglob("*") if p.is_file())
        self.assertEqual(before, after)
