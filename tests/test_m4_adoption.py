from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from artefact_sync import cli
from tests.helpers import make_repo, make_source_tree

# A source with CRLF endings and no final newline: both normalisations at once.
# The M4 probe corpus has neither, so this test is where that path stays covered.
CRLF_NOTE = b"# Cost model\r\n\r\nBuild versus buy."
PAGE = b"<html><head><title>P</title></head><body>Hi</body></html>\n"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin"}


def _commit(repo: Path, message: str) -> None:
    for args in (["add", "-A"], ["commit", "-q", "-m", message]):
        subprocess.run(["git", *args], cwd=repo, env=GIT_ENV, check=True)


def _seed_published_tree(repo: Path, source: Path) -> Path:
    """Publish once, commit, and hand back the pointer path.

    Committing matters: git normalises CRLF on commit under core.autocrlf=input, so
    the committed bytes are what a second machine - or a fresh clone - would see.
    """
    pointer = repo.parent / "pointer.json"
    cli.main(["init", "--pointer", str(pointer), "--repo", str(repo), "--source", str(source)])
    cli.main(["plan", "--pointer", str(pointer)])
    cli.main(["sync", "--pointer", str(pointer), "--yes"])
    _commit(repo, "publish")
    return pointer


class AdoptionTests(unittest.TestCase):
    def test_a_published_tree_is_not_rewritten_on_re_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"note.md": CRLF_NOTE, "page.html": PAGE})
            pointer = _seed_published_tree(repo, source)

            self.assertEqual(cli.EXIT_OK, cli.main(["plan", "--pointer", str(pointer)]))
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            # git status can report a line-ending-only change; the commit diff cannot.
            changed = subprocess.run(
                ["git", "diff", "--name-only", "HEAD", "--", "artefacts"],
                cwd=repo, capture_output=True, text=True,
            ).stdout
            self.assertEqual("", changed)

    def test_the_published_page_carries_no_carriage_returns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"note.md": CRLF_NOTE})
            _seed_published_tree(repo, source)
            page = (repo / "artefacts" / "note" / "index.html").read_bytes()
            self.assertNotIn(b"\r", page)
            self.assertIn(b"Build versus buy.\n", page)

    def test_a_manifest_committed_without_a_site_block_is_adoptable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"note.md": b"# n\n"})
            pointer = _seed_published_tree(repo, source)
            # Rewrite HEAD's manifest to the pre-site shape a real adopter has.
            path = repo / "artefacts" / "manifest.json"
            body = json.loads(path.read_text(encoding="utf-8"))
            body.pop("site")
            path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
            _commit(repo, "pre-site manifest")
            # Put the site block back in the working copy only, as adoption does.
            body["site"] = {"base_url": "https://x.example/artefacts/",
                            "catalogue": {"mode": "standalone"}}
            path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(cli.EXIT_OK, cli.main(["plan", "--pointer", str(pointer)]))
