from __future__ import annotations

import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from .config import ARTEFACTS_DIRNAME
from .errors import PublishError

GITHUB_REMOTE = re.compile(
    r"(?:git@github\.com:|https://github\.com/)([^/]+)/(.+?)(?:\.git)?/?$"
)


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


CommandRunner = Callable[[list[str], Path], CommandResult]
Fetcher = Callable[[str], int]


def subprocess_runner(args: list[str], cwd: Path) -> CommandResult:
    result = subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, check=False)
    return CommandResult(result.stdout, result.stderr, result.returncode)


def failure_message(result: CommandResult, failure: str) -> str:
    detail = result.stderr.strip() or result.stdout.strip()
    return f"{failure}: {detail}" if detail else failure


def run_checked(runner: CommandRunner, args: list[str], cwd: Path, failure: str) -> str:
    result = runner(args, cwd)
    if result.returncode != 0:
        raise PublishError(failure_message(result, failure))
    return result.stdout


def remote_url(repo_root: Path, runner: CommandRunner = subprocess_runner) -> str | None:
    result = runner(["git", "remote", "get-url", "origin"], repo_root)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def is_github(remote: str | None) -> bool:
    return bool(remote) and GITHUB_REMOTE.search(remote) is not None


def base_url_from_remote(remote: str) -> str | None:
    """The public base URL of the artefacts tree, or None for an unrecognised host.

    The trailing `artefacts/` segment is load-bearing: `plan` builds every public URL as
    `site.base_url + public_href(destination)`, and destinations are relative to `artefacts/`.
    """
    match = GITHUB_REMOTE.search(remote or "")
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    root = (
        f"https://{owner}.github.io/"
        if repo.lower() == f"{owner.lower()}.github.io"
        else f"https://{owner}.github.io/{repo}/"
    )
    return f"{root}{ARTEFACTS_DIRNAME}/"


def derive_base_url(repo_root: Path, runner: CommandRunner = subprocess_runner) -> str | None:
    remote = remote_url(repo_root, runner)
    return base_url_from_remote(remote) if remote else None


def fetch(url: str, timeout: float = 10.0) -> int:
    """The HTTP status for `url`, or 0 when the request never completed.

    Only http and https are followed. `base_url` comes out of the manifest, which is a file
    the user edits, so a `file:` URL here would turn URL verification into a local file read.
    """
    if urlsplit(url).scheme not in ("http", "https"):
        return 0
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, OSError, ValueError):
        return 0
