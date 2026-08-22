from __future__ import annotations

from pathlib import Path

from . import provider
from .config import ARTEFACTS_DIRNAME, Context
from .errors import PublishError
from .provider import CommandRunner, run_checked

COMMIT_MESSAGE = "chore: sync artefacts"
BRANCH_PREFIX = "artefact-sync"


def default_branch(repo_root: Path, runner: CommandRunner) -> str:
    """The branch `origin/HEAD` points at, or `main`.

    The prior art hardcoded `main`, which the design lists as site-specific surface.
    """
    result = runner(["git", "rev-parse", "--abbrev-ref", "origin/HEAD"], repo_root)
    name = result.stdout.strip()
    if result.returncode == 0 and name.startswith("origin/"):
        return name[len("origin/"):]
    return "main"


def working_tree_entries(repo_root: Path, runner: CommandRunner) -> list[tuple[str, str]]:
    """(status, path) pairs from `git status --porcelain -z`.

    `-z` rather than plain `--porcelain` because plain output quotes and escapes any path
    outside ASCII, and a path this function compares against a prefix must be literal. A
    rename or copy reports its old path as a second field, which the loop skips: the new
    path is the one that would enter the commit.
    """
    raw = run_checked(
        runner, ["git", "status", "--porcelain", "-z"], repo_root, "cannot read the working tree"
    )
    fields = [field for field in raw.split("\0") if field]
    entries = []
    index = 0
    while index < len(fields):
        status, path = fields[index][:2], fields[index][3:]
        entries.append((status, path))
        index += 2 if status[:1] in ("R", "C") else 1
    return entries


def preflight(context: Context, runner: CommandRunner) -> str:
    """Refuse to start unless a push can succeed and can only carry artefacts. Returns the branch."""
    run_checked(runner, ["git", "--version"], context.repo_root, "git is not available")
    remote = provider.remote_url(context.repo_root, runner)
    if remote is None:
        raise PublishError(
            "this repository has no 'origin' remote, so there is nowhere to publish\n\n"
            f"git -C {context.repo_root} remote add origin <url>"
        )
    if provider.is_github(remote):
        run_checked(
            runner, ["gh", "--version"], context.repo_root,
            "the GitHub CLI (gh) is not available, and publish needs it to watch the Pages build",
        )
        result = runner(["gh", "auth", "status"], context.repo_root)
        if result.returncode != 0:
            raise PublishError(
                provider.failure_message(result, "the GitHub CLI is not authenticated")
                + "\n\ngh auth login"
            )

    prefix = f"{ARTEFACTS_DIRNAME}/"
    outside = sorted(
        path
        for status, path in working_tree_entries(context.repo_root, runner)
        # Untracked files elsewhere cannot enter the commit: staging is `git add -- artefacts`.
        if status != "??" and not path.startswith(prefix)
    )
    if outside:
        raise PublishError(
            "the working tree has changes outside artefacts/: " + ", ".join(outside)
            + f"\n\ncommit or stash them first:\n  git -C {context.repo_root} stash push -- "
            + " ".join(outside)
        )

    branch = run_checked(
        runner, ["git", "branch", "--show-current"], context.repo_root,
        "cannot read the current branch",
    ).strip()
    default = default_branch(context.repo_root, runner)
    if branch != default:
        raise PublishError(
            f"publish must start on {default}, and this checkout is on {branch}\n\n"
            f"git -C {context.repo_root} switch {default}"
        )
    run_checked(
        runner, ["git", "fetch", "origin", default], context.repo_root,
        f"cannot fetch origin/{default}",
    )
    counts = run_checked(
        runner,
        ["git", "rev-list", "--left-right", "--count", f"{default}...origin/{default}"],
        context.repo_root,
        f"cannot compare {default} with origin/{default}",
    ).split()
    if counts != ["0", "0"]:
        ahead, behind = (counts + ["?", "?"])[:2]
        raise PublishError(
            f"local {default} and origin/{default} have diverged "
            f"({ahead} ahead, {behind} behind)\n\n"
            f"git -C {context.repo_root} pull --ff-only origin {default}"
        )
    return default


def commit_and_push(context: Context, branch: str, default: str, runner: CommandRunner) -> str:
    """Commit the applied artefacts tree and push it. Returns the new commit.

    The push is the irreversible step, so its failure carries recovery naming the commit that
    is sitting locally. Nothing here retries, resets or force-pushes: force-pushing someone's
    default branch over a transient network error is worse than the error.
    """
    if branch != default:
        run_checked(
            runner, ["git", "switch", "-c", branch], context.repo_root,
            f"cannot create branch {branch}",
        )
    # Stage the directory rather than the planned paths: applying a deletion can remove a file
    # git never tracked, whose path then matches nothing and aborts the whole `git add`.
    # `validate` has already proved artefacts/ holds exactly the expected set.
    run_checked(
        runner, ["git", "add", "--all", "--", ARTEFACTS_DIRNAME], context.repo_root,
        "cannot stage the artefact changes",
    )
    run_checked(
        runner, ["git", "commit", "-m", COMMIT_MESSAGE], context.repo_root,
        "cannot commit the artefact changes",
    )
    commit = run_checked(
        runner, ["git", "rev-parse", "HEAD"], context.repo_root, "cannot read the new commit"
    ).strip()

    result = runner(["git", "push", "origin", branch], context.repo_root)
    if result.returncode != 0:
        raise PublishError(
            provider.failure_message(result, f"cannot push {branch}")
            + f"\n\nCommit {commit[:12]} is committed locally and was not pushed. "
            "Nothing is live. When the network is back:\n"
            f"  git -C {context.repo_root} push origin {branch}"
        )
    return commit
