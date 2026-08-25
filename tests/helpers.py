from __future__ import annotations

import subprocess
from pathlib import Path

import provider


# One happy-path answer per command publish issues. A test overrides only the line it is about.
DEFAULT_RESPONSES = {
    "git --version": ("git version 2.39.0\n", "", 0),
    "gh --version": ("gh version 2.40.0\n", "", 0),
    "gh auth status": ("Logged in to github.com\n", "", 0),
    "git remote get-url origin": ("git@github.com:someone/notes.git\n", "", 0),
    "git status --porcelain -z": ("", "", 0),
    "git branch --show-current": ("main\n", "", 0),
    "git rev-parse --abbrev-ref origin/HEAD": ("origin/main\n", "", 0),
    "git fetch origin": ("", "", 0),
    "git rev-list --left-right --count": ("0\t0\n", "", 0),
    "git switch -c": ("", "", 0),
    "git add --all -- artefacts": ("", "", 0),
    "git commit -m": ("", "", 0),
    "git rev-parse HEAD": ("abc123def4567890\n", "", 0),
    "git push origin": ("", "", 0),
    "gh repo view --json nameWithOwner": ('{"nameWithOwner": "someone/notes"}\n', "", 0),
    "gh api repos/someone/notes/pages/builds/latest": (
        '{"status": "built", "commit": "abc123def4567890"}\n', "", 0
    ),
}


class RecordingRunner:
    """A fake CommandRunner. Records every argv and answers from a longest-prefix table."""

    def __init__(self, overrides: dict | None = None) -> None:
        self.calls: list = []
        self.table = dict(DEFAULT_RESPONSES)
        self.table.update(overrides or {})

    def __call__(self, args, cwd) -> provider.CommandResult:
        self.calls.append(list(args))
        joined = " ".join(args)
        for prefix in sorted(self.table, key=len, reverse=True):
            if joined.startswith(prefix):
                stdout, stderr, code = self.table[prefix]
                return provider.CommandResult(stdout, stderr, code)
        return provider.CommandResult("", f"unexpected command: {joined}", 127)

    def ran(self, prefix: str) -> list:
        return [call for call in self.calls if " ".join(call).startswith(prefix)]

    def index(self, prefix: str) -> int:
        """Position of the first matching call, or -1. Lets a test assert on ordering."""
        for position, call in enumerate(self.calls):
            if " ".join(call).startswith(prefix):
                return position
        return -1


class RecordingFetcher:
    """A fake Fetcher. Records every URL and answers 200 unless told otherwise."""

    def __init__(self, status: int = 200, overrides: dict | None = None) -> None:
        self.status = status
        self.overrides = dict(overrides or {})
        self.urls: list = []

    def __call__(self, url: str, timeout: float = 10.0) -> int:
        del timeout
        self.urls.append(url)
        return self.overrides.get(url, self.status)


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
