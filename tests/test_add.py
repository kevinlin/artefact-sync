from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from artefact_sync import cli
from tests.helpers import make_repo, make_source_tree


class AddTests(unittest.TestCase):
    def _fixture(self, tmp: str, files: dict | None = None) -> tuple[Path, Path, Path]:
        root = Path(tmp)
        repo = make_repo(root, {"README.md": b"x\n"})
        source = make_source_tree(root, files or {})
        pointer = root / "pointer.json"
        cli.main(["init", "--pointer", str(pointer),
                  "--repo", str(repo), "--source", str(source)])
        return repo, source, pointer

    def _entries(self, repo: Path) -> list:
        return json.loads((repo / "artefacts" / "manifest.json").read_text())["entries"]

    def _run(self, argv: list) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_an_outside_file_is_copied_and_published_in_one_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, source, pointer = self._fixture(tmp)
            elsewhere = Path(tmp) / "elsewhere"
            elsewhere.mkdir()
            (elsewhere / "Adoption Curve.png").write_bytes(b"PNGDATA")
            code, text = self._run(["add", str(elsewhere / "Adoption Curve.png"),
                                    "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_OK, code, text)
            self.assertEqual(b"PNGDATA", (source / "Adoption Curve.png").read_bytes())
            self.assertEqual(b"PNGDATA",
                             (repo / "artefacts" / "adoption-curve.png").read_bytes())
            entries = self._entries(repo)
        self.assertEqual(["Adoption Curve.png"], [entry["source"] for entry in entries])
        self.assertEqual("Adoption Curve", entries[0]["title"])
        self.assertNotIn("BLOCKED", text)

    def test_a_collision_in_the_source_folder_refuses_and_copies_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = self._fixture(tmp, {"curve.png": b"ORIGINAL"})
            elsewhere = Path(tmp) / "elsewhere"
            elsewhere.mkdir()
            (elsewhere / "curve.png").write_bytes(b"REPLACEMENT")
            code, text = self._run(["add", str(elsewhere / "curve.png"),
                                    "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_ERROR, code)
            self.assertEqual(b"ORIGINAL", (source / "curve.png").read_bytes())
        self.assertIn("already exists", text)

    def test_a_path_already_inside_the_source_folder_is_not_copied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, source, pointer = self._fixture(tmp, {"talk/curve.png": b"PNGDATA"})
            code, text = self._run(["add", str(source / "talk" / "curve.png"),
                                    "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_OK, code, text)
            self.assertFalse((source / "curve.png").exists())
            entries = self._entries(repo)
        self.assertEqual(["talk/curve.png"], [entry["source"] for entry in entries])
        self.assertEqual("talk/curve.png", entries[0]["destination"])

    def test_an_unapproved_extension_refuses_before_copying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = self._fixture(tmp)
            elsewhere = Path(tmp) / "notes.psd"
            elsewhere.write_bytes(b"binary")
            code, text = self._run(["add", str(elsewhere), "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_ERROR, code)
            self.assertFalse((source / "notes.psd").exists())
        self.assertIn(".psd", text)

    def test_a_name_matching_an_ignore_rule_refuses_before_copying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = self._fixture(tmp)
            elsewhere = Path(tmp) / "curve.local.png"
            elsewhere.write_bytes(b"PNGDATA")
            code, text = self._run(["add", str(elsewhere), "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_ERROR, code)
            self.assertFalse((source / "curve.local.png").exists())
        self.assertIn("ignored_sources", text)

    def test_another_unlisted_source_still_blocks_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, source, pointer = self._fixture(tmp, {"stranger.png": b"OTHER"})
            elsewhere = Path(tmp) / "curve.png"
            elsewhere.write_bytes(b"PNGDATA")
            code, text = self._run(["add", str(elsewhere), "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_BLOCKED, code)
            self.assertEqual(b"PNGDATA", (source / "curve.png").read_bytes())
            self.assertFalse((repo / "artefacts" / "curve.png").exists())
            sources = [entry["source"] for entry in self._entries(repo)]
        self.assertIn("stranger.png", text)
        self.assertEqual(["curve.png", "stranger.png"], sorted(sources))

    def test_declining_the_confirmation_applies_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, pointer = self._fixture(tmp)
            elsewhere = Path(tmp) / "curve.png"
            elsewhere.write_bytes(b"PNGDATA")
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer), unittest.mock.patch(
                "builtins.input", return_value="no"
            ):
                code = cli.main(["add", str(elsewhere), "--pointer", str(pointer)])
            self.assertEqual(cli.EXIT_ERROR, code)
            self.assertFalse((repo / "artefacts" / "curve.png").exists())
        self.assertIn("nothing was applied", buffer.getvalue())

    def test_a_directory_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = self._fixture(tmp)
            code, text = self._run(["add", str(source), "--pointer", str(pointer), "--yes"])
        self.assertEqual(cli.EXIT_ERROR, code)
        self.assertIn("not a regular file", text)
