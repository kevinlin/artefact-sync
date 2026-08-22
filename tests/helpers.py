from __future__ import annotations

import subprocess
from pathlib import Path


def _write(root: Path, files: dict[str, bytes]) -> Path:
    for relative, data in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return root


def make_source_tree(tmp: Path, files: dict[str, bytes]) -> Path:
    """A source folder. Keys are paths relative to the source root."""
    root = tmp / "source"
    root.mkdir(parents=True, exist_ok=True)
    return _write(root, files)


def make_repo(tmp: Path, files: dict[str, bytes]) -> Path:
    """A real git repo with one commit, so HEAD-diffing tests have a HEAD."""
    root = tmp / "repo"
    root.mkdir(parents=True, exist_ok=True)
    _write(root, files or {"README.md": b"repo\n"})
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin"}
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "seed"]):
        subprocess.run(["git", *args], cwd=root, env=env, check=True)
    return root
