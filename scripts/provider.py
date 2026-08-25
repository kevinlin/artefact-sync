from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from config import ARTEFACTS_DIRNAME
from errors import PublishError

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


BUILD_POLL_SECONDS = 5
BUILD_POLL_ATTEMPTS = 60


def _parse_json(output: str, description: str):
    try:
        return json.loads(output)
    except json.JSONDecodeError as error:
        raise PublishError(f"cannot parse {description}") from error


def repository_name(repo_root: Path, runner: CommandRunner) -> str:
    output = run_checked(
        runner, ["gh", "repo", "view", "--json", "nameWithOwner"], repo_root,
        "cannot identify the GitHub repository",
    )
    payload = _parse_json(output, "the GitHub repository")
    name = payload.get("nameWithOwner") if isinstance(payload, dict) else None
    if not name:
        raise PublishError("cannot parse the GitHub repository")
    return name


def wait_for_build(
    repo_root: Path, repository: str, commit: str,
    runner: CommandRunner, sleeper: Callable[[float], None],
) -> None:
    """Block until GitHub Pages has deployed `commit`.

    Only a build whose own `commit` matches is believed: a build that errored on an earlier
    commit says nothing about this one, and treating it as failure would abort a publish that
    is already live. Ported from artefacts.py:1975-1998.
    """
    for _ in range(BUILD_POLL_ATTEMPTS):
        output = run_checked(
            runner, ["gh", "api", f"repos/{repository}/pages/builds/latest"], repo_root,
            "cannot read the GitHub Pages build",
        )
        build = _parse_json(output, "the GitHub Pages build")
        if isinstance(build, dict) and build.get("commit") == commit:
            if build.get("status") == "built":
                return
            if build.get("status") == "errored":
                message = (build.get("error") or {}).get("message") or "unknown Pages error"
                raise PublishError(
                    f"the GitHub Pages build failed: {message}\n\n"
                    f"Commit {commit[:12]} is pushed and the site is not serving it. "
                    f"Fix the cause, then run 'artefact-sync publish' again."
                )
        sleeper(BUILD_POLL_SECONDS)
    minutes = BUILD_POLL_SECONDS * BUILD_POLL_ATTEMPTS // 60
    raise PublishError(
        f"GitHub Pages did not deploy {commit[:12]} within {minutes} minutes\n\n"
        f"The commit is pushed. Check the Pages settings for {repository}, then re-run "
        "'artefact-sync publish' to verify the URLs."
    )
