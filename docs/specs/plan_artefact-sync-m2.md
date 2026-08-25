# artefact-sync M2 Implementation Plan

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
[extraction-analysis.md](../history/extraction-analysis.md). M1's record, including the deviations
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

Created `artefact_sync/provider.py` housing the process/network seam: `CommandResult`,
`CommandRunner`, `subprocess_runner`, `run_checked`, `remote_url`, `base_url_from_remote`,
`derive_base_url`, `is_github`, and `fetch`. Added `PublishError` to `errors.py`. Moved
`derive_base_url` out of `cli.py` and corrected the base URL to include the `artefacts/` segment
(M1-a). Moved the three base-URL tests from `test_init.py` to `test_provider.py` with corrected
expectations.

### Task 2: `init` verifies the base URL it guessed

Added a single fetch of the guessed Pages URL at the end of `command_init`, so a wrong guess
surfaces at init time rather than at publish time. The fetch fires only when a remote produced a
guess; every existing fixture stays offline. Closes the M1-recorded gap.

### Task 3: `selfcheck.py` — the install integrity check

Created `artefact_sync/selfcheck.py` implementing a sub-second install integrity check (design D4).
Verifies bundled assets exist and are not truncated, both templates substitute cleanly, and a
Markdown page survives the render/extract round trip. Extracted `CATALOGUE_TEMPLATE_NAME` into
`catalogue.py` so the self-check and the renderer name the same file once.

### Task 4: extract `validate.py` from `cli.py`

Pure extraction (correction M2-b): moved `_ReferenceParser`, `_parse_references`,
`_local_reference`, and `validate_repository` from `cli.py` to a new `artefact_sync/validate.py`,
breaking the import cycle that would have blocked `publish.py` from calling validation.

### Task 5: `publish.py` — the recorded fake world, and preflight

Created `artefact_sync/publish.py` with `preflight`, `default_branch`, and
`working_tree_entries`. Built `RecordingRunner` and `RecordingFetcher` in `tests/helpers.py` —
the fake world all publish tests run against. Added `push` field to `config.Context` (defaulted
to `"direct"` so M1 constructions keep working). Preflight enforces: git available, gh
authenticated (GitHub only), no tracked changes outside `artefacts/`, checkout on default branch,
branch not diverged from origin.

### Task 6: `publish.py` — commit and push, in both push modes

Implemented `commit_and_push` supporting two modes (design D6): `direct` commits on the default
branch and pushes it; `branch` cuts a timestamped branch and pushes that. Staging is always
`git add --all -- artefacts` rather than named paths. A failed push names the local commit and the
retry command in its error; nothing force-pushes or resets.

### Task 7: the build wait and public URL verification

Added `repository_name` and `wait_for_build` to `provider.py`, porting the prior art's
`gh api repos/{owner}/{repo}/pages/builds/latest` poll. Only a build whose own commit matches the
pushed one is believed. Added `public_urls` and `verify_public_urls` to `publish.py` — URL
verification covers every entry plus `protected_files`, closing the gap where the prior art never
proved vendored `marked.min.js` was reachable.

### Task 8: `publish()` orchestration and the `publish` command

Wired the full orchestration: self-check → preflight → recompute → confirm → apply → validate →
commit → push → build wait → URL verification (correction M2-a's order). Added `BlockedPlan`,
`PublishResult`, `confirmation_text`, and the top-level `publish()` function. Wired
`command_publish` into `cli.py`. Protected-branch mode pushes a timestamped branch, prints the
compare URL, and stops without making anything live. Non-GitHub remotes get no build wait. A
declined confirmation applies nothing.

### Task 9: the acceptance run against a disposable Pages repository

Updated `SKILL.md` with the publish section and ran the full 15-step acceptance checklist against
`kevinlin/artefact-sync-probe`. All rows passed; the record is
[m2-acceptance.md](m2-acceptance.md). The run surfaced two M1-code defects (orphan note wording,
collection naming) deferred to M3 — no M2 code change was forced.

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

## Changelog

- 2026-08-23 — **Compacted post-implementation.** Removed step-by-step tasks, file-by-file diffs, code snippets, and verification commands now that the feature has shipped. Preserved Goal, Design Decisions, Critical Files summary, and follow-ups. Original plan recoverable via git history.
