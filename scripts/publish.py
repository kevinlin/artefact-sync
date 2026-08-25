from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import apply as apply_module, catalogue, plan as plan_module, provider
import validate as validate_module
from config import ARTEFACTS_DIRNAME, Context
from errors import ArtefactSyncError, PublishError
from manifest import Manifest
from plan import SyncPlan
from provider import CommandRunner, run_checked

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


def public_urls(context: Context, current: Manifest) -> tuple[str, ...]:
    """Every URL this publish makes a promise about, catalogue first.

    `protected_files` are included because the prior art's check omitted them, so a green
    publish never proved the vendored marked.min.js was reachable — and every Markdown page
    renders blank without it.
    """
    base = context.site.base_url
    urls = [base]
    if context.site.catalogue_mode == "inject" and context.site.catalogue_page is not None:
        urls.append(base + context.site.catalogue_page.as_posix())
    urls.extend(base + catalogue.public_href(entry) for entry in current.entries)
    urls.extend(base + path.as_posix() for path in current.protected_files)
    return tuple(dict.fromkeys(urls))


def verify_public_urls(urls: tuple[str, ...], fetcher: provider.Fetcher) -> None:
    for url in urls:
        status = fetcher(url)
        if status != 200:
            raise PublishError(
                f"published URL {url} returned "
                + (f"HTTP {status}" if status else "no response")
                + "\n\nThe commit is pushed and was not rolled back. Check the Pages build, "
                "then run 'artefact-sync publish' again to re-verify."
            )


class BlockedPlan(ArtefactSyncError):
    """The plan needs a human decision. Carries it so the CLI can write the proposal."""

    def __init__(self, plan: SyncPlan) -> None:
        super().__init__(f"{len(plan.blocked)} blocked item(s); nothing was published")
        self.plan = plan


@dataclass(frozen=True)
class PublishResult:
    branch: str
    commit: str
    live: bool
    catalogue_url: str
    verified_url_count: int


def confirmation_text(context: Context, sync_plan: SyncPlan) -> str:
    """The last gate before content is public. It spells out consequence, not operation."""
    added = sorted(
        (change for change in sync_plan.changes
         if change.kind == "add" and change.source is not None),
        key=lambda change: change.url,
    )
    removed = sorted(
        (change for change in sync_plan.changes if change.kind == "delete"),
        key=lambda change: change.url,
    )
    lines = [""]
    if added:
        lines.append(f"{len(added)} new public URL(s):")
        lines.extend(f"  {change.url}" for change in added)
    if removed:
        lines.append(f"{len(removed)} URL(s) will start returning 404:")
        lines.extend(f"  {change.url}" for change in removed)
    lines += [
        "",
        "Publishing is irreversible in practice. Search engines and readers cache a URL",
        "once it is public, and deleting the file later does not undo that.",
        "",
        f"Publish to {context.site.base_url}? Type yes to continue: ",
    ]
    return "\n".join(lines)


def _pull_request_hint(context: Context, runner: CommandRunner, default: str, branch: str) -> str:
    remote = provider.remote_url(context.repo_root, runner)
    match = provider.GITHUB_REMOTE.search(remote or "")
    if not match:
        return f"open a merge request from {branch} into {default} to make it live."
    return (
        "open the pull request:\n  "
        f"https://github.com/{match.group(1)}/{match.group(2)}/compare/"
        f"{default}...{branch}?expand=1"
    )


def publish(
    context: Context,
    current: Manifest,
    runner: CommandRunner = provider.subprocess_runner,
    fetcher: provider.Fetcher = provider.fetch,
    confirm=input,
    now=datetime.now,
    sleeper=time.sleep,
):
    """Make the artefacts tree live. Returns None when there was nothing to do.

    `validate` runs after `apply`, not before: it asserts every entry's destination exists,
    so running it first would reject any manifest holding an entry not yet written, which is
    every first publish of anything.
    """
    default = preflight(context, runner)
    sync_plan = plan_module.create_sync_plan(context, current)
    print(plan_module.format_plan(sync_plan), end="")
    if sync_plan.blocked:
        raise BlockedPlan(sync_plan)

    if not sync_plan.changes:
        urls = public_urls(context, sync_plan.next_manifest)
        verify_public_urls(urls, fetcher)
        print(f"nothing to publish; {len(urls)} published URLs verified.")
        return None

    if confirm(confirmation_text(context, sync_plan)) != "yes":
        print("publish cancelled; nothing was applied.")
        return None

    try:
        apply_module.apply_plan(context, sync_plan)
    except ArtefactSyncError as error:
        raise PublishError(
            f"{error}\n\nThe artefacts tree may be half written, and nothing was committed "
            "or pushed. Run 'artefact-sync sync' to converge it."
        ) from error

    try:
        notes = validate_module.validate_repository(context, sync_plan.next_manifest)
    except ArtefactSyncError as error:
        raise PublishError(
            f"{error}\n\nThe tree is applied and nothing was committed or pushed. "
            "Fix the cause, then run 'artefact-sync publish' again."
        ) from error
    for note in notes:
        print(f"warning: {note.kind} {note.where}: {note.detail}")

    branch = (
        default if context.push == "direct"
        else f"{BRANCH_PREFIX}/{now().strftime('%Y%m%d-%H%M%S')}"
    )
    commit = commit_and_push(context, branch, default, runner)

    if branch != default:
        print(f"pushed {branch}; nothing is live yet.")
        print(_pull_request_hint(context, runner, default, branch))
        return PublishResult(branch, commit, False, context.site.base_url, 0)

    if not provider.is_github(provider.remote_url(context.repo_root, runner)):
        print("this host exposes no build API, so the site may still be building; "
              "check the published URLs by hand.")
        return PublishResult(branch, commit, True, context.site.base_url, 0)

    repository = provider.repository_name(context.repo_root, runner)
    provider.wait_for_build(context.repo_root, repository, commit, runner, sleeper)
    urls = public_urls(context, sync_plan.next_manifest)
    verify_public_urls(urls, fetcher)
    return PublishResult(branch, commit, True, context.site.base_url, len(urls))
