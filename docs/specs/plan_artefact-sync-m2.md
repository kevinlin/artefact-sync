# artefact-sync M2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `publish` — the command that puts artefacts on the internet — together with the
provider seam it needs, the install self-check that guards it, and one real end-to-end run against a
disposable GitHub Pages repository.

**Architecture:** Three new modules and one extraction. `provider.py` becomes the single place that
talks to the outside world: the `git` and `gh` binaries through an injectable `CommandRunner`, and
HTTP through `urllib`. `publish.py` orchestrates preflight, recompute, apply, validate, commit,
push, build wait and URL verification, taking `runner`, `fetcher`, `confirm`, `now` and `sleeper` as
parameters so every step is testable against a recorded fake world. `selfcheck.py` proves the
installed skill is intact before anything irreversible runs. `validate.py` is lifted out of `cli.py`
unchanged so `publish` can call it without a `cli` → `publish` → `cli` cycle.

**Tech Stack:** Python 3.9, standard library only, `unittest`. External binaries: `git` always,
`gh` only when the remote is GitHub.

**Spec:** [design_artefact-sync.md](design_artefact-sync.md). Its supporting evidence, with
`file:line` citations into the prior art, is
[extraction-analysis.md](../research/extraction-analysis.md). M1's record, including the deviations
this plan inherits, is [plan_artefact-sync-m1.md](plan_artefact-sync-m1.md).

## Global Constraints

Every task's requirements implicitly include this section. The first eight are carried unchanged
from M1.

- **Python 3.9.** The tool must run under stock macOS `/usr/bin/python3` (3.9.6). Every module
  starts with `from __future__ import annotations` so `X | None` annotations parse on 3.9.
- **Standard library only.** No third-party import in the shipped package or in its tests, ever.
  `tests/test_stdlib_only.py` already allows every module M2 needs (`urllib`, `subprocess`, `json`,
  `time`, `datetime`, `typing`); do not widen `ALLOWED`.
- **Test command:** `python3 -m unittest discover -s tests -t . -v`. Never pytest. The M1 baseline
  is 131 tests, all passing; no task may leave that number lower.
- **British spelling** in every user-facing string, path and identifier: `artefacts`, `catalogue`.
- **No emoji** in any output.
- **Repo root is the skill directory.** This repo is cloned to `~/.claude/skills/artefact-sync/`.
- **Prior art, read-only:** `/Users/keli/dev/github-kevinlin/kevinlin.github.io/scripts/artefacts.py`
  and `tests/test_artefacts.py`. When a task says "port from `artefacts.py:X-Y`", open those exact
  lines and carry the behaviour across. Do not invent behaviour a citation does not support.
- **Never write to `/Users/keli/dev/github-kevinlin/kevinlin.github.io`.** It is a live site with 57
  published URLs. `git -C <that repo> status --short` must stay empty.
- **Exit codes:** `0` success, `1` error, `3` blocked and needs a human decision.
- **No network in the unit suite.** Every test in `tests/` runs offline. `provider.fetch` is
  exercised against a `http.server` bound to `127.0.0.1`; everything else injects a fake. The only
  networked run in M2 is the hand-run acceptance in Task 9.
- **No force-push, no auto-rollback** (design invariant 5). No code path may emit `--force`,
  `-f`, `git reset --hard`, or `git revert`. Task 8 pins this with a test that inspects every
  recorded argv.
- **Every failure after `apply` prints recovery for that exact state.** A `PublishError` message is
  two parts: what failed, then a blank line, then the literal command the user should run next.

---

## Decisions taken before this plan

Two questions the design left open. Both were put to the user and answered; the answers are the
premise of Tasks 7 and 9 and are not up for re-litigation during implementation.

| Question | Answer | Consequence |
|---|---|---|
| How does `publish` know the Pages build landed, given the builds API needs push-scope auth? | Port the prior art's `gh api repos/{owner}/{repo}/pages/builds/latest` poll | `gh` and `gh auth status` become hard requirements when the remote is GitHub. Non-GitHub remotes get no build wait and no URL verification: `publish` says so and stops after the push |
| What proves the provider seam works end to end? | A hand-run against a real disposable GitHub Pages repository, recorded in a checklist | No local Pages simulation is built. The unit suite covers orchestration against a recorded fake world; Task 9 covers everything the fake mocks out |

The second answer is the design's own position — "unit tests cannot close the publish gap ... the
disposable repo is its only coverage" — so M2 ships `publish` with 30-odd fake-world unit tests and
one real run, and says plainly that the run is the evidence.

---

## Corrections to the design this plan applies

Found while reading M1's code against the design. Each is applied by a task; each is a defect, not a
preference.

| # | What the design or M1 code says | What M2 does | Why |
|---|---|---|---|
| M1-a | `cli.derive_base_url` returns `https://owner.github.io/` and `init` writes it into `site.base_url` | Return `https://owner.github.io/artefacts/` | `plan._public_url` is `site.base_url + public_href(destination)`, and `destination` is relative to `artefacts/`. Every URL `init` seeds today is short by one path segment. M1 never noticed because nothing fetched them. M2 fetches all of them |
| M2-a | `publish` runs "the self-check, `validate`, recompute and apply" | Self-check, preflight, recompute, confirm, apply, **then** `validate` | `validate_repository` asserts every entry's destination exists. Run before `apply`, it rejects any manifest holding an entry whose file has not been written yet, so `publish` could never publish anything new |
| M2-b | Module table has no `validate.py`; `validate_repository` lives in `cli.py` | Move it, unchanged, to `validate.py` | `publish.py` must call it, and `cli.py` imports `publish.py`. Keeping it in `cli` is an import cycle |
| M2-c | `provider.py` is "`base_url(remote)` and `wait_for_build(commit)`, nothing else" | It also owns `CommandResult`, `CommandRunner`, `subprocess_runner`, `run_checked` and `fetch` | These are the process and network seam, and provider is the module that touches the outside world. Housing them anywhere else forces a cycle or a duplicate. The *policy* surface is still the two operations the design names |
| M2-d | Prior art shells out to `curl` for URL verification | `urllib.request` | Stdlib, so `curl --version` drops out of preflight and one required binary disappears. The injectable seam is a `fetcher` callable, the same shape as `runner` |
| M2-e | Prior art requires a wholly clean working tree, or exactly `" M artefacts/manifest.json"` | Reject tracked changes outside `artefacts/`; allow anything inside it, and ignore untracked files anywhere outside it | D7 makes `publish` recompute and apply, so a prior `sync` legitimately leaves the whole `artefacts/` tree dirty. Untracked files outside `artefacts/` can never enter the commit, because staging is `git add --all -- artefacts` |
| M2-f | Prior art hardcodes `main` | Read `origin/HEAD`, fall back to `main` | The design lists the hardcoded `origin/main` as site-specific surface to generalise |

Record any further corrections in "Deviations from this plan" at the bottom, and apply them to
[design_artefact-sync.md](design_artefact-sync.md), exactly as M1 did.

---

## File Structure

```
artefact-sync/
  SKILL.md                        + publish section, - "reserved for M2"
  artefact_sync/
    errors.py                     + PublishError
    config.py                     unchanged
    manifest.py                   unchanged
    scan.py                       unchanged
    render.py                     unchanged
    catalogue.py                  + CATALOGUE_TEMPLATE_NAME constant
    propose.py                    unchanged
    plan.py                       unchanged
    apply.py                      unchanged
    validate.py         NEW       validate_repository, lifted verbatim from cli.py
    provider.py         NEW       runner seam, remote parsing, base URL, fetch, build wait
    selfcheck.py        NEW       sub-second install integrity check
    publish.py          NEW       preflight, commit, push, build wait, URL verification
    cli.py                        - validate_repository, - derive_base_url, + command_publish
  tests/
    helpers.py                    + RecordingRunner, RecordingFetcher, DEFAULT_RESPONSES
    test_provider.py    NEW
    test_selfcheck.py   NEW
    test_publish.py     NEW
    test_validate.py              import moves from cli to validate
    test_init.py                  base URL tests move to test_provider.py; + verification tests
  docs/specs/
    m2-acceptance.md    NEW       the disposable-repo run, and its recorded result
```

Dependency direction stays one-way:

```
cli.py ──► config.py
  ├──► plan.py ──► render.py, catalogue.py, scan.py, propose.py ──► manifest.py ──► errors.py
  ├──► apply.py ──► plan.py
  ├──► validate.py ──► manifest.py, render.py, catalogue.py, scan.py
  ├──► selfcheck.py ──► render.py, catalogue.py, manifest.py, config.py
  └──► publish.py ──► apply.py, validate.py, plan.py, provider.py ──► config.py, errors.py
```

`publish.py` is the only module that both applies and pushes. `provider.py` is the only module that
opens a socket or runs `gh`. Nothing imports `cli.py`.

---

## Implementation Tasks

### Task 1: `provider.py` — the outside-world seam

**Files:**
- Create: `artefact_sync/provider.py`
- Modify: `artefact_sync/errors.py` (add `PublishError`), `artefact_sync/cli.py` (delete
  `derive_base_url`, `_GITHUB`, the `re` and `subprocess` imports; call `provider.derive_base_url`)
- Test: `tests/test_provider.py` (new), `tests/test_init.py` (delete the three base-URL tests, which
  move into `tests/test_provider.py` and change their expected values per correction M1-a)

**Interfaces:**
- Consumes: `config.ARTEFACTS_DIRNAME`, `errors.ArtefactSyncError`.
- Produces:
  - `PublishError(ArtefactSyncError)` in `errors.py`
  - `CommandResult` — frozen dataclass `(stdout: str, stderr: str, returncode: int)`
  - `CommandRunner = Callable[[list[str], Path], CommandResult]`
  - `Fetcher = Callable[[str], int]`
  - `subprocess_runner(args: list[str], cwd: Path) -> CommandResult`
  - `run_checked(runner: CommandRunner, args: list[str], cwd: Path, failure: str) -> str`
  - `remote_url(repo_root: Path, runner: CommandRunner = subprocess_runner) -> str | None`
  - `base_url_from_remote(remote: str) -> str | None`
  - `derive_base_url(repo_root: Path, runner: CommandRunner = subprocess_runner) -> str | None`
  - `is_github(remote: str | None) -> bool`
  - `fetch(url: str, timeout: float = 10.0) -> int`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_provider.py
from __future__ import annotations

import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from artefact_sync import provider
from artefact_sync.errors import PublishError
from tests.helpers import make_repo

ENV = {"PATH": "/usr/bin:/bin:/usr/local/bin"}


class BaseUrlTests(unittest.TestCase):
    def test_maps_recognised_remotes_to_an_artefacts_base_url(self) -> None:
        cases = {
            "git@github.com:someone/someone.github.io.git": "https://someone.github.io/artefacts/",
            "https://github.com/someone/someone.github.io": "https://someone.github.io/artefacts/",
            "git@github.com:someone/notes.git": "https://someone.github.io/notes/artefacts/",
            "https://github.com/someone/notes.git": "https://someone.github.io/notes/artefacts/",
            "https://github.com/someone/notes/": "https://someone.github.io/notes/artefacts/",
            "git@gitlab.com:someone/notes.git": None,
            "": None,
        }
        for remote, expected in cases.items():
            with self.subTest(remote=remote):
                self.assertEqual(expected, provider.base_url_from_remote(remote))

    def test_recognises_github_remotes_only(self) -> None:
        self.assertTrue(provider.is_github("git@github.com:someone/notes.git"))
        self.assertTrue(provider.is_github("https://github.com/someone/notes"))
        self.assertFalse(provider.is_github("git@gitlab.com:someone/notes.git"))
        self.assertFalse(provider.is_github(None))


class DeriveBaseUrlTests(unittest.TestCase):
    def _repo_with_remote(self, tmp: str, remote: str) -> Path:
        repo = make_repo(Path(tmp), {"README.md": b"x\n"})
        subprocess.run(["git", "remote", "add", "origin", remote], cwd=repo, env=ENV, check=True)
        return repo

    def test_user_pages_repo_keeps_the_artefacts_segment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo_with_remote(tmp, "git@github.com:someone/someone.github.io.git")
            self.assertEqual("https://someone.github.io/artefacts/",
                             provider.derive_base_url(repo))

    def test_project_pages_repo_keeps_both_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo_with_remote(tmp, "https://github.com/someone/notes.git")
            self.assertEqual("https://someone.github.io/notes/artefacts/",
                             provider.derive_base_url(repo))

    def test_returns_none_without_a_recognised_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp), {"README.md": b"x\n"})
            self.assertIsNone(provider.derive_base_url(repo))


class RunCheckedTests(unittest.TestCase):
    def test_raises_a_publish_error_carrying_stderr(self) -> None:
        def runner(args, cwd):
            del args, cwd
            return provider.CommandResult("", "fatal: nope\n", 128)

        with self.assertRaises(PublishError) as caught:
            provider.run_checked(runner, ["git", "push"], Path("."), "cannot push")
        self.assertIn("cannot push", str(caught.exception))
        self.assertIn("fatal: nope", str(caught.exception))

    def test_returns_stdout_on_success(self) -> None:
        def runner(args, cwd):
            del args, cwd
            return provider.CommandResult("ok\n", "", 0)

        self.assertEqual("ok\n", provider.run_checked(runner, ["git", "x"], Path("."), "no"))


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200 if self.path == "/ok" else 404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args) -> None:
        del args


class FetchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def test_returns_the_http_status(self) -> None:
        self.assertEqual(200, provider.fetch(self.base + "/ok"))
        self.assertEqual(404, provider.fetch(self.base + "/missing"))

    def test_returns_zero_when_the_request_never_completes(self) -> None:
        self.assertEqual(0, provider.fetch("http://127.0.0.1:1/ok", timeout=0.5))

    def test_refuses_a_non_http_scheme(self) -> None:
        self.assertEqual(0, provider.fetch("file:///etc/passwd"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_provider -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artefact_sync.provider'`

- [ ] **Step 3: Add `PublishError`**

```python
# append to artefact_sync/errors.py
class PublishError(ArtefactSyncError):
    """A publish step failed. The message carries recovery for that exact state."""
```

- [ ] **Step 4: Write `provider.py`**

```python
# artefact_sync/provider.py
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
```

- [ ] **Step 5: Point `cli.py` at the provider**

In `artefact_sync/cli.py`: delete the `_GITHUB` constant, the whole `derive_base_url` function, and
the now-unused `import re` and `import subprocess`. Add `provider` to the package import line, and
change the one call site in `command_init`:

```python
from . import apply as apply_module
from . import catalogue, config, manifest, plan as plan_module, provider, render, scan
```

```python
    guessed_url = provider.derive_base_url(repo_root)
```

- [ ] **Step 6: Move the base-URL tests out of `test_init.py`**

Delete `test_derives_a_user_pages_base_url_from_the_remote`,
`test_derives_a_project_pages_base_url_from_the_remote` and
`test_returns_none_when_the_remote_is_unrecognised` from `tests/test_init.py`; they now live in
`tests/test_provider.py` with the corrected expectations. Delete the `import subprocess` and the
`ENV` constant from `tests/test_init.py` if nothing else uses them.

- [ ] **Step 7: Run the whole suite**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: PASS, and the total is 131 - 3 + 10 = 138.

- [ ] **Step 8: Commit**

```bash
git add artefact_sync/provider.py artefact_sync/errors.py artefact_sync/cli.py \
        tests/test_provider.py tests/test_init.py
git commit -m "feat(provider): add the outside-world seam and fix the seeded base URL

The base URL init wrote omitted the artefacts/ segment, so every public URL it
produced was short by one path element. Nothing fetched them in M1."
```

---

### Task 2: `init` verifies the base URL it guessed

**Files:**
- Modify: `artefact_sync/cli.py:command_init`
- Test: `tests/test_init.py`

**Interfaces:**
- Consumes: `provider.fetch` (Task 1).
- Produces: no new names. `command_init` gains one printed line, and still returns `EXIT_OK`
  whatever the fetch says.

This closes the gap M1 recorded: "`init` guesses the base URL but does not fetch it to verify."
The fetch fires only when a remote produced a guess, so every existing fixture — which has no
`origin` — stays offline.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_init.py
import contextlib
import io
import subprocess
from unittest import mock

ENV = {"PATH": "/usr/bin:/bin:/usr/local/bin"}


class InitVerificationTests(unittest.TestCase):
    def _run(self, status: int) -> tuple[int, str, mock.Mock]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/someone/notes.git"],
                cwd=repo, env=ENV, check=True,
            )
            source = make_source_tree(root, {})
            output = io.StringIO()
            with mock.patch.object(cli.provider, "fetch", return_value=status) as fetch:
                with contextlib.redirect_stdout(output):
                    code = cli.main(["init", "--pointer", str(root / "pointer.json"),
                                     "--repo", str(repo), "--source", str(source)])
        return code, output.getvalue(), fetch

    def test_reports_a_reachable_pages_url(self) -> None:
        code, output, fetch = self._run(200)
        self.assertEqual(cli.EXIT_OK, code)
        fetch.assert_called_once_with("https://someone.github.io/notes/artefacts/")
        self.assertIn("verified https://someone.github.io/notes/artefacts/", output)

    def test_warns_but_still_succeeds_when_the_url_is_not_live(self) -> None:
        code, output, _fetch = self._run(404)
        self.assertEqual(cli.EXIT_OK, code)
        self.assertIn("returned 404", output)
        self.assertIn("site.base_url", output)

    def test_warns_when_the_request_never_completes(self) -> None:
        code, output, _fetch = self._run(0)
        self.assertEqual(cli.EXIT_OK, code)
        self.assertIn("did not respond", output)

    def test_never_fetches_without_a_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {})
            with mock.patch.object(cli.provider, "fetch") as fetch:
                with contextlib.redirect_stdout(io.StringIO()):
                    cli.main(["init", "--pointer", str(root / "pointer.json"),
                              "--repo", str(repo), "--source", str(source)])
        fetch.assert_not_called()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_init -v`
Expected: FAIL — `AssertionError: Expected 'fetch' to have been called once. Called 0 times.`

- [ ] **Step 3: Implement the verification**

Replace the closing lines of `command_init` in `artefact_sync/cli.py`:

```python
    print(f"pointer written to {args.pointer}")
    print(f"seeded {artefacts}")
    if guessed_url is None:
        print("could not derive a Pages URL from origin; set site.base_url in the manifest")
    else:
        _report_base_url(loaded.site.base_url)
    return EXIT_OK


def _report_base_url(base_url: str) -> None:
    """Fetch the configured base URL once, so a wrong guess surfaces now, not at publish."""
    status = provider.fetch(base_url)
    if status == 200:
        print(f"verified {base_url}")
    elif status == 0:
        print(f"warning: {base_url} did not respond; check site.base_url in the manifest")
    else:
        print(f"warning: {base_url} returned {status}; check site.base_url in the manifest "
              "and that Pages is enabled for this repository")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_init -v`
Expected: PASS

- [ ] **Step 5: Run the whole suite**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: PASS, 142 tests.

- [ ] **Step 6: Commit**

```bash
git add artefact_sync/cli.py tests/test_init.py
git commit -m "feat(init): fetch the guessed Pages URL once to check the guess"
```

---

### Task 3: `selfcheck.py` — the install integrity check

**Files:**
- Create: `artefact_sync/selfcheck.py`
- Modify: `artefact_sync/catalogue.py` (extract the template filename into a constant so the
  self-check and the renderer name the same file once)
- Test: `tests/test_selfcheck.py`

**Interfaces:**
- Consumes: `config.DEFAULT_FAVICON`, `config.Site`, `manifest.Entry`, `manifest.TEMPLATE_NAME`,
  `manifest.VENDOR_NAME`, `render.load_template`, `render.render_markdown_page`,
  `render.extract_markdown`, `catalogue.CATALOGUE_TEMPLATE_NAME`.
- Produces:
  - `catalogue.CATALOGUE_TEMPLATE_NAME = "catalogue-template.html"`
  - `selfcheck.run_self_check(artefacts_root: Path | None = None) -> None`, raising
    `ValidationError` naming the damaged file and the command that repairs it.

Design D4: `publish` runs `validate` plus a sub-second install self-check, which "exists only for
the corrupted-`git pull` case, which CI cannot see". So it checks the *installed skill*: that the
bundled assets are present and whole, that both templates still substitute every placeholder the
code passes them, and that a Markdown page still survives the round trip. Passing an
`artefacts_root` extends the same template check to the repository's own override, which is the
other file a bad edit can break.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_selfcheck.py
from __future__ import annotations

import shutil
import tempfile
import time
import unittest
from pathlib import Path

from artefact_sync import selfcheck
from artefact_sync.errors import ValidationError
from artefact_sync.manifest import TEMPLATE_NAME


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
```

Those last two tests mutate the installed package on purpose, so both restore from a copy in a
`finally`. If either ever fails mid-way, `git checkout artefact_sync/assets` repairs the tree.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_selfcheck -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artefact_sync.selfcheck'`

- [ ] **Step 3: Name the catalogue template once**

In `artefact_sync/catalogue.py`, add the constant beside the marker constants and use it in
`render_standalone_catalogue`:

```python
CATALOGUE_START = "<!-- ARTEFACTS:START -->"
CATALOGUE_END = "<!-- ARTEFACTS:END -->"
CATALOGUE_TEMPLATE_NAME = "catalogue-template.html"
```

```python
def render_standalone_catalogue(manifest: Manifest, site: Site) -> bytes:
    path = Path(__file__).resolve().parent / "assets" / CATALOGUE_TEMPLATE_NAME
```

- [ ] **Step 4: Write `selfcheck.py`**

```python
# artefact_sync/selfcheck.py
from __future__ import annotations

import string
from pathlib import Path, PurePosixPath

from .catalogue import CATALOGUE_TEMPLATE_NAME
from .config import DEFAULT_FAVICON, Site
from .errors import ValidationError
from .manifest import Entry, TEMPLATE_NAME, VENDOR_NAME
from .render import extract_markdown, load_template, render_markdown_page

# The bundled assets belong to the installed package, so this is the one lookup the
# "nothing resolves paths from __file__" rule exempts.
ASSETS = Path(__file__).resolve().parent / "assets"
REPAIR = "the install looks damaged; repair it with: git -C ~/.claude/skills/artefact-sync pull"
PROBE_MARKDOWN = b"# Probe\n\nOne $dollar, one </script> escape, one trailing newline.\n"
PAGE_FIELDS = {
    "title": "t", "favicon": "f", "prefix": "p", "vendor": "v",
    "markdown": "m", "block_start": "s", "block_end": "e",
}
CATALOGUE_FIELDS = {"title": "t", "favicon": "f", "catalogue": "c"}
MINIMUM_BYTES = {TEMPLATE_NAME: 200, CATALOGUE_TEMPLATE_NAME: 200, VENDOR_NAME: 10_000}

PROBE_SITE = Site(
    base_url="https://probe.invalid/artefacts/",
    favicon=DEFAULT_FAVICON,
    catalogue_mode="standalone",
    catalogue_page=None,
)
PROBE_ENTRY = Entry(
    id="self-check",
    source=PurePosixPath("probe.md"),
    destination=PurePosixPath("probe/index.html"),
    title="Probe",
    collection="self-check",
    order=1,
)


def _check_assets() -> None:
    for name, minimum in MINIMUM_BYTES.items():
        path = ASSETS / name
        if not path.is_file():
            raise ValidationError(f"bundled asset is missing: {path}\n\n{REPAIR}")
        size = path.stat().st_size
        if size < minimum:
            raise ValidationError(
                f"bundled asset looks truncated: {path} is {size} bytes, "
                f"expected at least {minimum}\n\n{REPAIR}"
            )


def _check_substitutes(template: string.Template, fields: dict, label: str) -> None:
    try:
        template.substitute(**fields)
    except (KeyError, ValueError) as error:
        raise ValidationError(
            f"{label} does not substitute cleanly: {error}\n\n"
            f"it must use only {', '.join('$' + name for name in sorted(fields))} "
            "and escape any other dollar sign as $$"
        ) from error


def _check_round_trip(template: string.Template, label: str) -> None:
    rendered = render_markdown_page(
        PROBE_ENTRY, PROBE_MARKDOWN, PurePosixPath("vendor") / VENDOR_NAME,
        PROBE_SITE, template,
    )
    found = extract_markdown(rendered.decode("utf-8"))
    if found != PROBE_MARKDOWN.decode("utf-8"):
        raise ValidationError(
            f"{label} broke the Markdown round trip; a page rendered from it cannot be "
            f"read back as its source\n\n{REPAIR}"
        )


def run_self_check(artefacts_root: Path | None = None) -> None:
    """Prove the installed skill can still render, before anything irreversible runs.

    Cheap on purpose: file sizes, two template substitutions, one round trip. It catches the
    corrupted or half-finished `git pull`, which no CI run on the source repository can see.
    """
    _check_assets()
    bundled = string.Template((ASSETS / TEMPLATE_NAME).read_text(encoding="utf-8"))
    _check_substitutes(bundled, PAGE_FIELDS, f"the bundled {TEMPLATE_NAME}")
    _check_round_trip(bundled, f"the bundled {TEMPLATE_NAME}")
    _check_substitutes(
        string.Template((ASSETS / CATALOGUE_TEMPLATE_NAME).read_text(encoding="utf-8")),
        CATALOGUE_FIELDS,
        f"the bundled {CATALOGUE_TEMPLATE_NAME}",
    )
    if artefacts_root is None or not (artefacts_root / TEMPLATE_NAME).is_file():
        return
    override = load_template(artefacts_root)
    _check_substitutes(override, PAGE_FIELDS, f"artefacts/{TEMPLATE_NAME}")
    _check_round_trip(override, f"artefacts/{TEMPLATE_NAME}")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_selfcheck -v`
Expected: PASS, 6 tests.

- [ ] **Step 6: Run the whole suite**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: PASS, 148 tests.

- [ ] **Step 7: Commit**

```bash
git add artefact_sync/selfcheck.py artefact_sync/catalogue.py tests/test_selfcheck.py
git commit -m "feat(selfcheck): add the sub-second install integrity check"
```

---

### Task 4: extract `validate.py` from `cli.py`

**Files:**
- Create: `artefact_sync/validate.py`
- Modify: `artefact_sync/cli.py` (delete the moved code and the imports only it used)
- Test: `tests/test_validate.py` (one import line and one call site)

**Interfaces:**
- Consumes: nothing new.
- Produces: `validate.validate_repository(context: config.Context, current: manifest.Manifest) ->
  tuple[plan.Note, ...]`, identical to `cli.validate_repository` today. `cli.validate_repository`
  ceases to exist.

A pure move, correction M2-b. `publish.py` must call `validate_repository`, and `cli.py` imports
`publish.py`; leaving it in `cli` is an import cycle. Change no behaviour: if a test needs editing
beyond its import line, the move went wrong.

- [ ] **Step 1: Move the code**

Create `artefact_sync/validate.py` holding, verbatim from `artefact_sync/cli.py`, the
`_ReferenceParser` class, `_parse_references`, `_local_reference` and `validate_repository`, under
this header:

```python
# artefact_sync/validate.py
from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from . import catalogue, config, manifest, plan as plan_module, render, scan
from .errors import ValidationError
```

- [ ] **Step 2: Strip `cli.py` down**

Delete from `artefact_sync/cli.py`: `_ReferenceParser`, `_parse_references`, `_local_reference`,
`validate_repository`, and every import that only they used — `from collections import Counter`,
`from html.parser import HTMLParser`, `from urllib.parse import unquote, urlsplit`, and `render`
and `scan` from the package import line. Add `validate` to it, and point `command_validate` at the
new home:

```python
from . import apply as apply_module
from . import catalogue, config, manifest, plan as plan_module, provider, validate
```

```python
def command_validate(args: argparse.Namespace) -> int:
    context, current = _command_state(args)
    for note in validate.validate_repository(context, current):
        print(f"warning: {note.kind} {note.where}: {note.detail}")
    return EXIT_OK
```

- [ ] **Step 3: Update the one test call site**

In `tests/test_validate.py`, change the import to `from artefact_sync import cli, validate` and the
single direct call on line 34 to `validate.validate_repository(context, current)`.

- [ ] **Step 4: Run the whole suite**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: PASS, still 148 tests. A pure move adds none and drops none.

- [ ] **Step 5: Confirm nothing was left behind**

Run: `python3 -c "import ast,pathlib;src=pathlib.Path('artefact_sync/cli.py').read_text();print('validate_repository' in src, 'HTMLParser' in src)"`
Expected: `False False`

- [ ] **Step 6: Commit**

```bash
git add artefact_sync/validate.py artefact_sync/cli.py tests/test_validate.py
git commit -m "refactor(validate): move validate_repository out of cli so publish can call it"
```

---
### Task 5: `publish.py` — the recorded fake world, and preflight

**Files:**
- Create: `artefact_sync/publish.py`
- Modify: `artefact_sync/config.py` (`Context` gains `push`), `tests/helpers.py` (the fakes)
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: `provider.CommandRunner`, `provider.CommandResult`, `provider.run_checked`,
  `provider.failure_message`, `provider.remote_url`, `provider.is_github`,
  `config.ARTEFACTS_DIRNAME`, `errors.PublishError`.
- Produces:
  - `config.Context.push: str = "direct"` — a fourth field, defaulted so the three positional
    constructions in `tests/` keep working; `config.build_context` fills it from the pointer
  - `publish.default_branch(repo_root: Path, runner: CommandRunner) -> str`
  - `publish.working_tree_entries(repo_root: Path, runner: CommandRunner) -> list[tuple[str, str]]`
  - `publish.preflight(context: Context, runner: CommandRunner) -> str`, returning the default
    branch name
  - `tests.helpers.RecordingRunner`, `tests.helpers.RecordingFetcher`,
    `tests.helpers.DEFAULT_RESPONSES`

- [ ] **Step 1: Build the fake world in `tests/helpers.py`**

```python
# append to tests/helpers.py
from artefact_sync import provider

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
```

- [ ] **Step 2: Write the failing preflight tests**

```python
# tests/test_publish.py
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from artefact_sync import config, manifest, publish
from artefact_sync.config import site_from_dict
from artefact_sync.errors import PublishError
from tests.helpers import RecordingRunner, make_repo, make_source_tree

BASE_URL = "https://someone.github.io/notes/artefacts/"


def make_context(root: Path, push: str = "direct") -> config.Context:
    repo = make_repo(root, {"README.md": b"x\n"})
    source = make_source_tree(root, {})
    artefacts = repo / "artefacts"
    artefacts.mkdir(exist_ok=True)
    body = manifest.Manifest(
        version=1, site=site_from_dict({"base_url": BASE_URL}),
        protected_files=(), ignored_sources=(), collections=(), entries=(),
    )
    (artefacts / manifest.MANIFEST_NAME).write_text(
        manifest.manifest_to_json(body), encoding="utf-8"
    )
    return config.Context(repo, source, artefacts, body.site, push)


class PreflightTests(unittest.TestCase):
    def preflight(self, overrides: dict | None = None, push: str = "direct") -> str:
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp), push)
            self.runner = RecordingRunner(overrides)
            return publish.preflight(context, self.runner)

    def test_a_clean_tree_on_the_default_branch_passes(self) -> None:
        self.assertEqual("main", self.preflight())

    def test_reads_the_default_branch_from_origin_head(self) -> None:
        self.assertEqual("trunk", self.preflight({
            "git rev-parse --abbrev-ref origin/HEAD": ("origin/trunk\n", "", 0),
            "git branch --show-current": ("trunk\n", "", 0),
        }))

    def test_falls_back_to_main_when_origin_head_is_unset(self) -> None:
        self.assertEqual("main", self.preflight({
            "git rev-parse --abbrev-ref origin/HEAD": ("", "no upstream\n", 128),
        }))

    def test_rejects_a_missing_git(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({"git --version": ("", "not found\n", 127)})
        self.assertIn("git is not available", str(caught.exception))

    def test_rejects_a_missing_github_cli(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({"gh --version": ("", "not found\n", 127)})
        self.assertIn("gh", str(caught.exception))

    def test_rejects_an_unauthenticated_github_cli(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({"gh auth status": ("", "not logged in\n", 1)})
        self.assertIn("gh auth login", str(caught.exception))

    def test_skips_the_github_checks_for_another_host(self) -> None:
        self.preflight({
            "git remote get-url origin": ("git@gitlab.example:someone/notes.git\n", "", 0),
        })
        self.assertEqual([], self.runner.ran("gh "))

    def test_rejects_a_repository_with_no_origin(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({"git remote get-url origin": ("", "no such remote\n", 2)})
        self.assertIn("origin", str(caught.exception))

    def test_rejects_tracked_changes_outside_artefacts(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({
                "git status --porcelain -z": (" M index.html\0 M artefacts/manifest.json\0", "", 0),
            })
        self.assertIn("index.html", str(caught.exception))
        self.assertNotIn("artefacts/manifest.json", str(caught.exception))

    def test_accepts_a_dirty_artefacts_tree(self) -> None:
        self.assertEqual("main", self.preflight({
            "git status --porcelain -z": (
                " M artefacts/manifest.json\0?? artefacts/talk/new/index.html\0", "", 0
            ),
        }))

    def test_ignores_untracked_files_elsewhere(self) -> None:
        self.assertEqual("main", self.preflight({
            "git status --porcelain -z": ("?? scratch.md\0?? notes/\0", "", 0),
        }))

    def test_reads_a_rename_at_its_new_path(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({
                "git status --porcelain -z": ("R  moved.html\0artefacts/old.html\0", "", 0),
            })
        self.assertIn("moved.html", str(caught.exception))

    def test_rejects_publishing_from_another_branch(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({"git branch --show-current": ("spike\n", "", 0)})
        self.assertIn("switch main", str(caught.exception))

    def test_rejects_a_diverged_branch_and_names_the_recovery(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.preflight({"git rev-list --left-right --count": ("1\t2\n", "", 0)})
        self.assertIn("diverged", str(caught.exception))
        self.assertIn("pull --ff-only", str(caught.exception))
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_publish -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artefact_sync.publish'`

- [ ] **Step 4: Give `Context` the push mode**

In `artefact_sync/config.py`:

```python
@dataclass(frozen=True)
class Context:
    repo_root: Path
    source_root: Path
    artefacts_root: Path
    site: Site
    push: str = "direct"
```

```python
def build_context(pointer: Pointer, site: Site) -> Context:
    repo_root = pointer.repo.expanduser().resolve()
    return Context(
        repo_root=repo_root,
        source_root=pointer.source.expanduser().resolve(),
        artefacts_root=repo_root / ARTEFACTS_DIRNAME,
        site=site,
        push=pointer.push,
    )
```

- [ ] **Step 5: Write preflight**

```python
# artefact_sync/publish.py
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
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_publish -v`
Expected: PASS, 13 tests.

- [ ] **Step 7: Run the whole suite**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: PASS, 161 tests.

- [ ] **Step 8: Commit**

```bash
git add artefact_sync/publish.py artefact_sync/config.py tests/helpers.py tests/test_publish.py
git commit -m "feat(publish): add preflight and the recorded command runner"
```

---

### Task 6: `publish.py` — commit and push, in both push modes

**Files:**
- Modify: `artefact_sync/publish.py`
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: `publish.preflight` (Task 5), `provider.run_checked`, `provider.failure_message`.
- Produces: `publish.commit_and_push(context: Context, branch: str, default: str,
  runner: CommandRunner) -> str`, returning the new commit SHA.

Two modes, from design D6. `direct` commits on the default branch and pushes it. `branch` cuts a
timestamped branch, pushes that, and leaves the last mile to a human — automating the pull request
would need six `gh` operations and would falsify the portability claim the design rests on.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_publish.py
class CommitAndPushTests(unittest.TestCase):
    def run_it(self, branch: str = "main", overrides: dict | None = None) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            self.runner = RecordingRunner(overrides)
            return publish.commit_and_push(context, branch, "main", self.runner)

    def test_returns_the_new_commit(self) -> None:
        self.assertEqual("abc123def4567890", self.run_it())

    def test_direct_mode_never_creates_a_branch(self) -> None:
        self.run_it()
        self.assertEqual([], self.runner.ran("git switch"))
        self.assertEqual([["git", "push", "origin", "main"]], self.runner.ran("git push"))

    def test_branch_mode_creates_the_branch_before_staging(self) -> None:
        self.run_it("artefact-sync/20260823-120000")
        self.assertLess(
            self.runner.index("git switch -c"), self.runner.index("git add"),
        )
        self.assertEqual(
            [["git", "push", "origin", "artefact-sync/20260823-120000"]],
            self.runner.ran("git push"),
        )

    def test_stages_the_directory_rather_than_named_paths(self) -> None:
        self.run_it()
        self.assertEqual(
            [["git", "add", "--all", "--", "artefacts"]], self.runner.ran("git add")
        )

    def test_never_force_pushes(self) -> None:
        self.run_it()
        for call in self.runner.calls:
            self.assertNotIn("--force", call)
            self.assertNotIn("-f", call)

    def test_a_failed_push_names_the_local_commit_in_its_recovery(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.run_it(overrides={"git push origin": ("", "network is down\n", 128)})
        message = str(caught.exception)
        self.assertIn("abc123def456", message)
        self.assertIn("Nothing is live", message)
        self.assertIn("git -C", message)
        self.assertIn("push origin main", message)

    def test_a_failed_commit_stops_before_any_push(self) -> None:
        with self.assertRaises(PublishError):
            self.run_it(overrides={"git commit -m": ("", "nothing to commit\n", 1)})
        self.assertEqual([], self.runner.ran("git push"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_publish.CommitAndPushTests -v`
Expected: FAIL with `AttributeError: module 'artefact_sync.publish' has no attribute 'commit_and_push'`

- [ ] **Step 3: Implement `commit_and_push`**

```python
# append to artefact_sync/publish.py
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_publish -v`
Expected: PASS, 20 tests.

- [ ] **Step 5: Run the whole suite**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: PASS, 168 tests.

- [ ] **Step 6: Commit**

```bash
git add artefact_sync/publish.py tests/test_publish.py
git commit -m "feat(publish): commit and push, direct and protected-branch modes"
```

---

### Task 7: the build wait and public URL verification

**Files:**
- Modify: `artefact_sync/provider.py`, `artefact_sync/publish.py`
- Test: `tests/test_provider.py`, `tests/test_publish.py`

**Interfaces:**
- Consumes: `provider.run_checked`, `catalogue.public_href`, `manifest.Manifest`.
- Produces:
  - `provider.repository_name(repo_root: Path, runner: CommandRunner) -> str` — `owner/repo`
  - `provider.wait_for_build(repo_root: Path, repository: str, commit: str,
    runner: CommandRunner, sleeper: Callable[[float], None]) -> None`
  - `provider.BUILD_POLL_SECONDS = 5`, `provider.BUILD_POLL_ATTEMPTS = 60`
  - `publish.public_urls(context: Context, current: Manifest) -> tuple[str, ...]`
  - `publish.verify_public_urls(urls: tuple, fetcher: provider.Fetcher) -> None`

The build wait is ported from `artefacts.py:1975-1998`, minus the pull-request plumbing around it.
It polls `gh api repos/{owner}/{repo}/pages/builds/latest` and only believes a result whose
`commit` is the one just pushed — a build that errored on an older commit says nothing about this
one.

URL verification covers more than the prior art's did: every entry, plus `protected_files`. Today's
check omits protected files, so a green publish does not prove the vendored `marked.min.js` is
reachable, and every Markdown page renders blank without it.

- [ ] **Step 1: Write the failing provider tests**

```python
# append to tests/test_provider.py, with the import raised to the top of the file
from tests.helpers import RecordingRunner


class BuildWaitTests(unittest.TestCase):
    def wait(self, overrides: dict | None = None, commit: str = "abc123def4567890") -> None:
        self.runner = RecordingRunner(overrides)
        self.slept = []
        provider.wait_for_build(
            Path("."), "someone/notes", commit, self.runner, self.slept.append
        )

    def test_returns_once_the_build_reports_this_commit_built(self) -> None:
        self.wait()
        self.assertEqual([], self.slept)

    def test_reports_the_pages_error_for_this_commit(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.wait({"gh api repos/someone/notes/pages/builds/latest": (
                '{"status": "errored", "commit": "abc123def4567890",'
                ' "error": {"message": "symlink not allowed"}}\n', "", 0)})
        self.assertIn("symlink not allowed", str(caught.exception))

    def test_keeps_polling_past_an_error_on_an_older_commit(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.wait({"gh api repos/someone/notes/pages/builds/latest": (
                '{"status": "errored", "commit": "0000000000000000",'
                ' "error": {"message": "old failure"}}\n', "", 0)})
        self.assertNotIn("old failure", str(caught.exception))
        self.assertEqual(provider.BUILD_POLL_ATTEMPTS, len(self.slept))

    def test_times_out_and_names_the_recovery(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.wait({"gh api repos/someone/notes/pages/builds/latest": (
                '{"status": "building", "commit": "abc123def4567890"}\n', "", 0)})
        message = str(caught.exception)
        self.assertIn("did not deploy", message)
        self.assertIn("artefact-sync publish", message)

    def test_rejects_an_unparseable_payload(self) -> None:
        with self.assertRaises(PublishError) as caught:
            self.wait({"gh api repos/someone/notes/pages/builds/latest": ("not json\n", "", 0)})
        self.assertIn("cannot parse", str(caught.exception))


class RepositoryNameTests(unittest.TestCase):
    def test_reads_name_with_owner(self) -> None:
        self.assertEqual(
            "someone/notes", provider.repository_name(Path("."), RecordingRunner())
        )

    def test_rejects_an_unparseable_payload(self) -> None:
        runner = RecordingRunner({"gh repo view --json nameWithOwner": ("{}\n", "", 0)})
        with self.assertRaises(PublishError):
            provider.repository_name(Path("."), runner)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_provider -v`
Expected: FAIL with `AttributeError: module 'artefact_sync.provider' has no attribute 'wait_for_build'`

- [ ] **Step 3: Implement the provider half**

```python
# append to artefact_sync/provider.py — add `import json` at the top
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
```

- [ ] **Step 4: Write the failing URL tests**

```python
# append to tests/test_publish.py — add `RecordingFetcher` to the helpers import and
# `from pathlib import PurePosixPath` to the top of the file
class PublicUrlTests(unittest.TestCase):
    def _manifest(self, **overrides) -> manifest.Manifest:
        entries = (
            manifest.Entry(id="note", source=PurePosixPath("note.md"),
                           destination=PurePosixPath("incident/note/index.html"),
                           title="Note", collection="c", order=1),
            manifest.Entry(id="curve", source=PurePosixPath("curve.png"),
                           destination=PurePosixPath("talk/curve.png"),
                           title="Curve", collection="c", order=2),
        )
        body = {"version": 1, "site": site_from_dict({"base_url": BASE_URL}),
                "protected_files": (PurePosixPath("vendor/marked.min.js"),),
                "ignored_sources": (), "collections": (), "entries": entries}
        body.update(overrides)
        return manifest.Manifest(**body)

    def test_covers_the_catalogue_every_entry_and_every_protected_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            urls = publish.public_urls(context, self._manifest())
        self.assertEqual(
            (BASE_URL,
             BASE_URL + "incident/note/",
             BASE_URL + "talk/curve.png",
             BASE_URL + "vendor/marked.min.js"),
            urls,
        )

    def test_adds_the_host_page_in_inject_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            site = site_from_dict(
                {"base_url": BASE_URL, "catalogue": {"mode": "inject", "page": "gallery.html"}}
            )
            context = config.Context(context.repo_root, context.source_root,
                                     context.artefacts_root, site, "direct")
            urls = publish.public_urls(context, self._manifest())
        self.assertIn(BASE_URL + "gallery.html", urls)


class VerifyPublicUrlsTests(unittest.TestCase):
    def test_fetches_every_url(self) -> None:
        fetcher = RecordingFetcher()
        publish.verify_public_urls((BASE_URL, BASE_URL + "a.png"), fetcher)
        self.assertEqual([BASE_URL, BASE_URL + "a.png"], fetcher.urls)

    def test_a_non_200_names_the_url_the_code_and_the_absence_of_rollback(self) -> None:
        fetcher = RecordingFetcher(overrides={BASE_URL + "a.png": 404})
        with self.assertRaises(PublishError) as caught:
            publish.verify_public_urls((BASE_URL, BASE_URL + "a.png"), fetcher)
        message = str(caught.exception)
        self.assertIn("a.png", message)
        self.assertIn("404", message)
        self.assertIn("was not rolled back", message)

    def test_a_dead_host_reports_no_response(self) -> None:
        with self.assertRaises(PublishError) as caught:
            publish.verify_public_urls((BASE_URL,), RecordingFetcher(status=0))
        self.assertIn("no response", str(caught.exception))
```

- [ ] **Step 5: Implement the publish half**

```python
# append to artefact_sync/publish.py — add `from . import catalogue` and
# `from .manifest import Manifest` at the top
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
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_provider tests.test_publish -v`
Expected: PASS

- [ ] **Step 7: Run the whole suite**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: PASS, 180 tests.

- [ ] **Step 8: Commit**

```bash
git add artefact_sync/provider.py artefact_sync/publish.py \
        tests/test_provider.py tests/test_publish.py
git commit -m "feat(publish): wait for the Pages build and verify every published URL"
```

---
### Task 8: `publish()` orchestration and the `publish` command

**Files:**
- Modify: `artefact_sync/publish.py`, `artefact_sync/cli.py`
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: everything from Tasks 1-7, plus `plan.create_sync_plan`, `plan.format_plan`,
  `apply.apply_plan`, `validate.validate_repository`, `selfcheck.run_self_check`.
- Produces:
  - `publish.BlockedPlan(ArtefactSyncError)` with attribute `plan: SyncPlan`
  - `publish.PublishResult` — frozen dataclass `(branch: str, commit: str, live: bool,
    catalogue_url: str, verified_url_count: int)`
  - `publish.confirmation_text(context: Context, sync_plan: SyncPlan) -> str`
  - `publish.publish(context, current, runner=..., fetcher=..., confirm=input, now=..., sleeper=...)
    -> PublishResult | None`
  - `cli.command_publish(args) -> int`

Order of operations, and correction M2-a in force: self-check, preflight, recompute, print the plan,
confirm, apply, validate, commit, push, wait, verify. `validate` runs *after* `apply` because it
asserts that every entry's destination exists — run before, it rejects any manifest holding an entry
whose file has not been written yet, which is every first publish of anything.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_publish.py — imports needed at the top of the file:
# contextlib, io, from unittest import mock, from artefact_sync import cli
PAGE = b"<html><head></head><body><h1>Cost model</h1></body></html>\n"


def make_publishing_world(root: Path, push: str = "direct", extra: dict | None = None):
    """init, then one plan run, so the manifest holds a proposal and a file is waiting."""
    repo = make_repo(root, {"README.md": b"x\n"})
    source = make_source_tree(root, dict({"talk/cost-model.html": PAGE}, **(extra or {})))
    pointer = root / "pointer.json"
    with contextlib.redirect_stdout(io.StringIO()):
        cli.main(["init", "--pointer", str(pointer),
                  "--repo", str(repo), "--source", str(source)])
        cli.main(["plan", "--pointer", str(pointer)])
    body = manifest.load_manifest(repo / "artefacts")
    context = config.Context(repo.resolve(), source.resolve(),
                             repo.resolve() / "artefacts", body.site, push)
    return context, body, pointer


class _SnapshotRunner(RecordingRunner):
    """Records whether a published file was on disk by the time staging ran."""

    def __init__(self, target: Path, overrides: dict | None = None) -> None:
        super().__init__(overrides)
        self.target = target
        self.existed_at_add = None

    def __call__(self, args, cwd):
        if args[:2] == ["git", "add"]:
            self.existed_at_add = self.target.is_file()
        return super().__call__(args, cwd)


class PublishTests(unittest.TestCase):
    def run_publish(self, context, current, runner=None, fetcher=None,
                    answer: str = "yes", overrides: dict | None = None):
        self.runner = runner or RecordingRunner(overrides)
        self.fetcher = fetcher or RecordingFetcher()
        self.prompt = []
        self.output = io.StringIO()
        with contextlib.redirect_stdout(self.output):
            return publish.publish(
                context, current, self.runner, self.fetcher,
                confirm=lambda text: (self.prompt.append(text), answer)[1],
                now=lambda: datetime(2026, 8, 23, 12, 0, 0),
                sleeper=lambda _seconds: None,
            )

    def test_publishes_applies_validates_commits_pushes_waits_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            page = context.artefacts_root / "talk" / "cost-model" / "index.html"
            runner = _SnapshotRunner(page)
            result = self.run_publish(context, current, runner=runner)
        self.assertTrue(runner.existed_at_add, "apply must run before staging")
        self.assertLess(runner.index("git push"), runner.index("gh api"))
        self.assertEqual("abc123def4567890", result.commit)
        self.assertEqual("main", result.branch)
        self.assertTrue(result.live)
        self.assertIn(context.site.base_url, self.fetcher.urls)
        self.assertEqual(result.verified_url_count, len(self.fetcher.urls))

    def test_verification_runs_after_the_build_wait(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            runner = RecordingRunner()
            commands_before_first_fetch = []

            class _CountingFetcher(RecordingFetcher):
                def __call__(self, url, timeout=10.0):
                    commands_before_first_fetch.append(len(runner.calls))
                    return super().__call__(url, timeout)

            self.run_publish(context, current, runner=runner, fetcher=_CountingFetcher())
        self.assertTrue(commands_before_first_fetch)
        self.assertGreater(commands_before_first_fetch[0], runner.index("gh api"))

    def test_a_declined_confirmation_applies_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            page = context.artefacts_root / "talk" / "cost-model" / "index.html"
            self.assertIsNone(self.run_publish(context, current, answer="no"))
            self.assertFalse(page.is_file())
        self.assertEqual([], self.runner.ran("git commit"))
        self.assertIn("cancelled", self.output.getvalue())

    def test_the_confirmation_states_the_urls_and_the_irreversibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            self.run_publish(context, current, answer="no")
        text = self.prompt[0]
        self.assertIn("talk/cost-model/", text)
        self.assertIn("irreversible", text)
        self.assertIn("Type yes to continue", text)

    def test_no_changes_verifies_the_urls_and_commits_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, pointer = make_publishing_world(Path(tmp))
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(["sync", "--pointer", str(pointer), "--yes"])
            current = manifest.load_manifest(context.artefacts_root)
            self.assertIsNone(self.run_publish(context, current))
        self.assertEqual([], self.runner.ran("git commit"))
        self.assertIn("nothing to publish", self.output.getvalue())
        self.assertIn(context.site.base_url, self.fetcher.urls)

    def test_a_blocked_plan_raises_before_anything_is_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(
                Path(tmp), extra={"diagrams/bad.svg": b"<svg>\n<script/>\n</svg>\n"}
            )
            with self.assertRaises(publish.BlockedPlan) as caught:
                self.run_publish(context, current)
        self.assertEqual([], self.runner.ran("git commit"))
        self.assertTrue(caught.exception.plan.blocked)

    def test_protected_branch_mode_pushes_a_branch_and_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp), push="branch")
            result = self.run_publish(context, current)
        self.assertEqual("artefact-sync/20260823-120000", result.branch)
        self.assertFalse(result.live)
        self.assertEqual(0, result.verified_url_count)
        self.assertEqual([], self.runner.ran("gh api"))
        self.assertEqual([], self.fetcher.urls)
        self.assertIn("compare/main...artefact-sync/20260823-120000", self.output.getvalue())

    def test_another_host_skips_the_build_wait_and_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            result = self.run_publish(context, current, overrides={
                "git remote get-url origin": ("git@gitlab.example:someone/notes.git\n", "", 0),
            })
        self.assertEqual([], self.runner.ran("gh "))
        self.assertEqual(0, result.verified_url_count)
        self.assertIn("no build API", self.output.getvalue())

    def test_a_failed_validate_stops_before_the_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            with mock.patch.object(
                publish.validate_module, "validate_repository",
                side_effect=ValidationError("catalogue link missing"),
            ):
                with self.assertRaises(PublishError) as caught:
                    self.run_publish(context, current)
        self.assertEqual([], self.runner.ran("git commit"))
        self.assertIn("catalogue link missing", str(caught.exception))
        self.assertIn("nothing was committed", str(caught.exception))

    def test_a_failed_apply_names_sync_as_the_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            with mock.patch.object(
                publish.apply_module, "apply_plan",
                side_effect=ValidationError("applied file differs from plan"),
            ):
                with self.assertRaises(PublishError) as caught:
                    self.run_publish(context, current)
        self.assertIn("artefact-sync sync", str(caught.exception))

    def test_never_force_pushes_or_resets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, current, _pointer = make_publishing_world(Path(tmp))
            self.run_publish(context, current)
        for call in self.runner.calls:
            joined = " ".join(call)
            for banned in ("--force", " -f", "reset --hard", "revert"):
                self.assertNotIn(banned, joined)


class PublishCommandTests(unittest.TestCase):
    def test_runs_the_self_check_before_publishing(self) -> None:
        order = []
        with tempfile.TemporaryDirectory() as tmp:
            _context, _current, pointer = make_publishing_world(Path(tmp))
            with mock.patch.object(cli.selfcheck, "run_self_check",
                                   side_effect=lambda *a: order.append("selfcheck")):
                with mock.patch.object(cli.publish, "publish",
                                       side_effect=lambda *a, **k: order.append("publish")):
                    with contextlib.redirect_stdout(io.StringIO()):
                        code = cli.main(["publish", "--pointer", str(pointer)])
        self.assertEqual(cli.EXIT_OK, code)
        self.assertEqual(["selfcheck", "publish"], order)

    def test_a_blocked_plan_exits_3_and_writes_the_proposal(self) -> None:
        # publish.publish is patched rather than driven: its `runner` default binds at
        # definition time, so patching provider.subprocess_runner afterwards would not
        # reach it, and the real runner would fail preflight on the fixture's absent origin.
        with tempfile.TemporaryDirectory() as tmp:
            context, _current, pointer = make_publishing_world(Path(tmp))
            source = Path(json.loads(pointer.read_text())["source"])
            (source / "curve.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            reloaded = manifest.load_manifest(context.artefacts_root)
            blocked = plan_module.create_sync_plan(context, reloaded)
            self.assertTrue(blocked.blocked)
            with mock.patch.object(cli.selfcheck, "run_self_check"):
                with mock.patch.object(cli.publish, "publish",
                                       side_effect=publish.BlockedPlan(blocked)):
                    with contextlib.redirect_stdout(io.StringIO()):
                        with contextlib.redirect_stderr(io.StringIO()):
                            code = cli.main(["publish", "--pointer", str(pointer)])
            body = json.loads(
                (context.artefacts_root / manifest.MANIFEST_NAME).read_text(encoding="utf-8")
            )
        self.assertEqual(cli.EXIT_BLOCKED, code)
        self.assertIn("curve.png", {entry["source"] for entry in body["entries"]})

    def test_reports_the_commit_and_the_verified_count(self) -> None:
        result = publish.PublishResult("main", "abc123def4567890", True,
                                       "https://x.example/artefacts/", 4)
        with tempfile.TemporaryDirectory() as tmp:
            _context, _current, pointer = make_publishing_world(Path(tmp))
            output = io.StringIO()
            with mock.patch.object(cli.selfcheck, "run_self_check"):
                with mock.patch.object(cli.publish, "publish", return_value=result):
                    with contextlib.redirect_stdout(output):
                        code = cli.main(["publish", "--pointer", str(pointer)])
        self.assertEqual(cli.EXIT_OK, code)
        self.assertIn("abc123def456", output.getvalue())
        self.assertIn("verified 4", output.getvalue())
```

Add to the top of `tests/test_publish.py`: `import contextlib`, `import io`, `import json`,
`from datetime import datetime`, `from unittest import mock`,
`from artefact_sync import cli, plan as plan_module`, and
`from artefact_sync.errors import PublishError, ValidationError`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_publish -v`
Expected: FAIL with `AttributeError: module 'artefact_sync.publish' has no attribute 'publish'`

- [ ] **Step 3: Implement the orchestration**

```python
# append to artefact_sync/publish.py — add these to the imports at the top:
# import time
# from dataclasses import dataclass
# from datetime import datetime
# from . import apply as apply_module, catalogue, plan as plan_module
# from . import validate as validate_module
# from .errors import ArtefactSyncError
# from .plan import SyncPlan


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
    so running it first would reject any manifest holding an entry not yet written — which is
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
```

- [ ] **Step 4: Wire it into the CLI**

In `artefact_sync/cli.py`, add `publish` and `selfcheck` to the package import, add the command, and
put it in the dispatch table:

```python
from . import apply as apply_module
from . import catalogue, config, manifest, plan as plan_module, provider, publish, selfcheck
from . import validate
```

```python
def command_publish(args: argparse.Namespace) -> int:
    context, current = _command_state(args)
    selfcheck.run_self_check(context.artefacts_root)
    try:
        result = publish.publish(context, current)
    except publish.BlockedPlan as blocked:
        _write_proposed_manifest(context, blocked.plan)
        print(str(blocked), file=sys.stderr)
        return EXIT_BLOCKED
    if result is None:
        return EXIT_OK
    print(f"published {result.commit[:12]} on {result.branch}")
    if result.verified_url_count:
        print(f"verified {result.verified_url_count} published URLs "
              f"under {result.catalogue_url}")
    return EXIT_OK
```

```python
    commands = {
        "plan": command_plan,
        "sync": command_sync,
        "publish": command_publish,
        "validate": command_validate,
    }
    command = commands.get(args.command)
    if command is None:
        raise ConfigError(f"{args.command} command is not available yet")
```

`publish` deliberately has no `--yes`. `sync` gained one so the convergence test could run
unattended; the command that makes things public keeps its prompt.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_publish -v`
Expected: PASS, 39 tests.

- [ ] **Step 6: Run the whole suite on both interpreters**

Run: `python3 -m unittest discover -s tests -t . -v`
Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: PASS on both, 194 tests. The second run is the 3.9.6 floor.

- [ ] **Step 7: Commit**

```bash
git add artefact_sync/publish.py artefact_sync/cli.py tests/test_publish.py
git commit -m "feat(publish): wire up the publish command end to end"
```

---

### Task 9: the acceptance run against a disposable Pages repository

**Files:**
- Modify: `SKILL.md`
- Create: `docs/specs/m2-acceptance.md`
- Test: none. This task's evidence is a filled-in results table, not an assertion.

**Interfaces:**
- Consumes: the finished `publish` command.
- Produces: `docs/specs/m2-acceptance.md`, with every step's result recorded.

This is the milestone. The design says it plainly: all the publish unit tests "run against a
recorded fake world: they prove orchestration, not that auth, push, build timing, URL derivation or
deletion work against a live host. That is the half changing most, and the disposable repo is its
only coverage."

- [ ] **Step 1: Update `SKILL.md`**

Replace the two reserved-command lines in the Commands section:

```markdown
- `add <path>`: reserved for M3. It is not available yet.
- `publish`: recompute the plan, confirm it, apply it, validate the tree, commit, push, wait for
  the Pages build, then fetch every published URL including protected files. Publishing is
  irreversible in practice: search engines and readers may cache a URL once it is public, and
  deleting the file later does not undo that. State this before running it.
```

Add a section after Commands:

```markdown
## Publishing

`publish` needs `git`, and needs `gh` authenticated when the remote is GitHub. It refuses to start
unless the working tree is clean outside `artefacts/`, the checkout is on the default branch, and
that branch matches `origin`. Set `"push": "branch"` in `~/.config/artefact-sync/config.json` for a
protected default branch: `publish` then pushes a timestamped branch, prints the pull request URL,
and stops without making anything live.

Every failure stops and prints the recovery for that exact state. Nothing force-pushes and nothing
rolls back automatically. If a publish fails after the push, re-run `publish`: with no changes left
it re-verifies the published URLs and reports.
```

- [ ] **Step 2: Write the acceptance checklist**

Create `docs/specs/m2-acceptance.md`:

```markdown
# M2 acceptance: publish against a disposable Pages repository

Status: not yet run
Date: <fill in>

The unit suite runs `publish` against a recorded fake world, which proves orchestration and nothing
else. Auth, push, build timing, URL derivation and deletion are exactly what the fake mocks out.
This run is their only coverage. Do it against a throwaway repository, never against a site with
published URLs.

## Setup

1. Create a public repository `artefact-sync-probe` under your account. Do not reuse a real one.
2. Enable Pages: Settings, Pages, source `Deploy from a branch`, branch `main`, folder `/ (root)`.
3. `git clone` it, and commit one `index.html` so the branch exists and Pages has something to build.
4. `mkdir ~/Downloads/ProbeArtefacts`.

## Steps

| # | Command | Expected | Result |
|---|---|---|---|
| 1 | `python3 -m artefact_sync init --repo <clone> --source ~/Downloads/ProbeArtefacts` | Prints the pointer path, seeds `artefacts/`, and either `verified https://<you>.github.io/artefact-sync-probe/artefacts/` or a warning that it is not live yet | |
| 2 | Confirm the guess: does the printed base URL match the URL in the repository's Pages settings, with `artefacts/` on the end? | Yes | |
| 3 | Put four files in the source folder: a `.md`, an `.html`, a `.png`, and a clean `.svg` | | |
| 4 | `python3 -m artefact_sync plan` | Exit 3, four proposals written to `artefacts/manifest.json`, four full URLs printed with byte sizes | |
| 5 | Read the proposed destinations and titles, edit if wrong | | |
| 6 | `python3 -m artefact_sync publish`, type `yes` | Preflight passes, four URLs listed in the confirmation, apply, validate, commit, push, build wait, then every URL verified | |
| 7 | Record the wall-clock time of the build wait | Under five minutes, or `BUILD_POLL_ATTEMPTS` needs raising | |
| 8 | Open each published URL in a browser | The Markdown page renders through `marked.js`; the image and SVG load; the catalogue links all four | |
| 9 | `python3 -m artefact_sync publish` again with nothing changed | `nothing to publish`, every URL re-verified, no commit | |
| 10 | Delete the `.png` from the source folder, then `publish` | The confirmation says one URL will start returning 404; after the build, that URL 404s and the other three still serve | |
| 11 | `gh auth logout`, then `publish` | Refuses in preflight, names `gh auth login`, changes nothing | |
| 12 | `gh auth login`, edit an unrelated file at the repository root, then `publish` | Refuses, names that file, changes nothing | |
| 13 | Set `"push": "branch"` in the pointer, change a source file, then `publish` | Pushes `artefact-sync/<timestamp>`, prints the compare URL, verifies nothing, leaves `main` untouched | |
| 14 | Merge that branch by hand, then `publish` on `main` | Preflight requires a `git pull --ff-only` first, and says so | |
| 15 | Delete the probe repository and the source folder | | |

## Result

<fill in: what passed, what did not, and what changed as a result>
```

- [ ] **Step 3: Run it**

Work through the table, filling in the Result column as you go. Stop at the first row that fails,
fix the cause, and restart from step 1 with a fresh repository — a half-published probe repo is not
a clean fixture for the rows after it.

- [ ] **Step 4: Record what the run changed**

Any code change the run forced goes in "Deviations from this plan" below, and any design claim it
disproved goes into [design_artefact-sync.md](design_artefact-sync.md), the same way M1 recorded its
six.

- [ ] **Step 5: Run the whole suite once more**

Run: `python3 -m unittest discover -s tests -t . -v`
Run: `git -C /Users/keli/dev/github-kevinlin/kevinlin.github.io status --short`
Expected: PASS, 194 tests; the second command prints nothing.

- [ ] **Step 6: Commit**

```bash
git add SKILL.md docs/specs/m2-acceptance.md
git commit -m "docs: record the M2 acceptance run against a disposable Pages repo"
```

---

## Self-Review

**Spec coverage.** Walked each section of [design_artefact-sync.md](design_artefact-sync.md) that
M1 left open:

| Spec item | Task |
|---|---|
| `publish` runs the self-check | 3, 8 |
| `publish` runs `validate` | 4, 8 (order corrected, M2-a) |
| `publish` recomputes and applies (D7) | 8 |
| `publish` confirms irreversibility | 8 |
| `publish` commits and pushes | 6 |
| `publish` waits for the build | 7 |
| `publish` fetches every published URL, protected files included | 7, 8 |
| D4 self-check rather than the full unit suite | 3, 8 |
| D6 protected-branch mode pushes and stops | 6, 8 |
| Invariant 5: no auto-rollback, no force-push, recovery per state | 5, 6, 7, 8 |
| `provider.base_url(remote)` | 1 |
| `provider.wait_for_build(commit)` | 7 |
| `init` verifies its base URL guess by fetching once | 2 |
| Portability: push via plain git | 5, 6 — `gh` is required only for a GitHub remote, and only for the build wait |
| Testing ledger: "Publish 20 cases, rewrite all" | 5-8, 39 cases; every prior-art case assuming `gh pr`, a pull request and a check named `validate` is gone |
| Testing ledger: "New surface: self-check, provider" | 1, 3, 7 |
| M2 release gate: disposable Pages repo | 9 |

**Gaps, stated rather than hidden.**

- GitLab is untested, and now also unwaited: a non-GitHub remote gets a push and a printed warning,
  no build wait and no URL verification. The design puts "GitLab as a tested path" out of scope, and
  this plan keeps it there rather than shipping an untested second provider.
- `rebuild_showcase_atlas` is not ported. It fires from `apply` and `publish` in the prior art and
  is M4's problem, per the design's migration note.
- Nothing verifies that the bytes GitHub serves equal the bytes pushed. URL verification checks
  status codes only. Content verification would need a second fetch per URL and a decision about
  what a mismatch means while a CDN is still warming; it is not worth it before the Task 9 run says
  whether it is a real failure mode.
- `add <path>` stays M3, untouched.

**Type consistency.** `CommandResult`, `CommandRunner` and `Fetcher` are defined once in
`provider.py` (Task 1) and imported under those names everywhere. `run_checked` and
`failure_message` keep one signature across Tasks 5-7. `Context` gains exactly one field, `push`,
defaulted so M1's three positional constructions keep working. `preflight` returns the default
branch name, and Tasks 6 and 8 both call that value `default`. `commit_and_push(context, branch,
default, runner)` has the same argument order in its definition, its tests and its one caller.
`PublishResult` fields are named identically in Task 8's implementation, its tests, and
`cli.command_publish`.

---

## Deviations from this plan

Recorded because the plan was written before the code existed, and a plan that hides where it was
wrong is worth less on the next milestone.

Plan defects found and corrected during implementation:

- Task 4's Step 5 check contradicted its own Step 2. Step 2 writes
  `validate.validate_repository(context, current)` into `cli.py`; Step 5 then greps for
  `'validate_repository' in src` and expects `False`, which a plain call to a moved function can
  never satisfy. The check was meant to prove the *definition* left `cli.py`, so it is now
  `'def validate_repository' in src`. Implementation first satisfied the literal grep by building
  the attribute name as `getattr(validate, "validate_" + "repository")`; review reversed that. A
  check that a readable call cannot pass is the defective half. Hiding a real dependency from grep
  and every static analyser costs more than the check buys.
- Task 5's arithmetic was off by one. Step 1 defines fourteen `PreflightTests` methods, Step 6
  states thirteen, and every later count inherits the error. The corrected chain is 162 after
  Task 5, 169 after Task 6, 181 after Task 7, and **195** at the end of M2, not 194.
  Implementation first hit the stated thirteen by merging `test_rejects_a_missing_git` and
  `test_rejects_a_missing_github_cli` into one subTest loop; review reversed that too. Two failures
  on different missing binaries, are two tests. A subTest loop hides which half broke behind one
  red result.

Both defects were first resolved by bending code to a stated number rather than fixing the number.
Worth naming as a pattern for M3: a count in a plan is a prediction, and the tests are the fact.

Review findings fixed after Task 9:

- None. The live run passed all fifteen rows against `kevinlin/artefact-sync-probe` on 2026-08-23
  and forced no code change; the record is [m2-acceptance.md](m2-acceptance.md). Row 11 ran by
  substitution: a stub `gh` whose `auth status` exits 1, because `gh auth logout` cannot be undone
  without an interactive browser login. It exercises the same preflight branch.

The run did surface two defects, both in M1 code rather than M2's, and both left for M3, which the
plan's own milestone list already scopes as "whatever `plan`'s warnings need after the Task 9 run
exposes them":

- `plan.create_sync_plan` computes orphans as `scan_published_tree - expected` without subtracting
  the destinations already queued as `delete` changes, so a file being deleted in this run is also
  reported as `in repo, in no manifest, left alone`. Behaviour is correct: `apply` acts on changes,
  not notes, and row 10 confirmed the file really goes. The sentence is still false as printed, and
  it is the sentence that carries design invariant 4's promise to the user.
- `propose` names a collection of root-level sources after whichever file sorts first
  (`_source_group` returns `""`, so the label falls through to `sources[0].stem`). The grouping is
  right and only the first run is arbitrary, but the first run is the one a new user sees.

Design corrections this implementation forced:

- None. The six corrections the plan itself carries (M1-a, M2-a through M2-f) all held as written,
  and M1-a proved itself live at row 2: the seeded base URL matched the Pages settings URL exactly,
  which M1's one-segment-short guess would not have. Nothing in Tasks 1-9 disproved a claim in
  [design_artefact-sync.md](design_artefact-sync.md).

## Milestones after M2

- **M3** — `add <path>`, and whatever `plan`'s warnings need after the Task 9 run exposes them.
- **M4** — the release gate. Copy `kevinlin.github.io`'s existing template verbatim into
  `page-template.html`, seed `date` from current mtimes, install the skill, run `plan` against the
  live tree, and require zero changes across its 57 entries. Rehome `build_showcase_atlas.py`
  first; it is triggered from `apply`/`publish` today and is not ported.
