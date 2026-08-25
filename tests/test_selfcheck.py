from __future__ import annotations

import shutil
import tempfile
import time
import unittest
from pathlib import Path

import selfcheck
from errors import ValidationError
from manifest import TEMPLATE_NAME


class SelfCheckTests(unittest.TestCase):
    def test_a_clean_install_passes(self) -> None:
        selfcheck.run_self_check()

    def test_it_is_sub_second(self) -> None:
        started = time.monotonic()
        selfcheck.run_self_check()
        self.assertLess(time.monotonic() - started, 1.0)

    def test_a_repository_template_with_an_unknown_placeholder_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artefacts = Path(tmp) / "artefacts"
            artefacts.mkdir()
            (artefacts / TEMPLATE_NAME).write_text(
                "<html>$title costs $mystery</html>\n", encoding="utf-8"
            )
            with self.assertRaises(ValidationError) as caught:
                selfcheck.run_self_check(artefacts)
        self.assertIn(TEMPLATE_NAME, str(caught.exception))
        self.assertIn("mystery", str(caught.exception))

    def test_a_repository_template_that_drops_the_markdown_block_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artefacts = Path(tmp) / "artefacts"
            artefacts.mkdir()
            (artefacts / TEMPLATE_NAME).write_text(
                "<html><head>$favicon<title>$title</title></head>"
                "<body>$prefix$vendor$block_start$block_end</body></html>\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValidationError) as caught:
                selfcheck.run_self_check(artefacts)
        self.assertIn("round trip", str(caught.exception))

    def test_a_missing_bundled_asset_fails_and_names_the_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spare = Path(tmp) / "assets"
            shutil.copytree(selfcheck.ASSETS, spare)
            damaged = selfcheck.ASSETS / "marked.min.js"
            try:
                damaged.unlink()
                with self.assertRaises(ValidationError) as caught:
                    selfcheck.run_self_check()
            finally:
                shutil.copyfile(spare / "marked.min.js", damaged)
        self.assertIn("marked.min.js", str(caught.exception))
        self.assertIn("git -C", str(caught.exception))

    def test_a_truncated_bundled_asset_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spare = Path(tmp) / "assets"
            shutil.copytree(selfcheck.ASSETS, spare)
            damaged = selfcheck.ASSETS / "page-template.html"
            try:
                damaged.write_text("", encoding="utf-8")
                with self.assertRaises(ValidationError):
                    selfcheck.run_self_check()
            finally:
                shutil.copyfile(spare / "page-template.html", damaged)
