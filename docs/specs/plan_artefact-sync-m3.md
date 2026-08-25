# artefact-sync M3 Implementation Plan

**Status: complete.** All six tasks implemented; 227 tests pass on both `/usr/bin/python3` (3.9.6,
the floor) and 3.13. Each task landed in its specified commit, with one extra test-driver cleanup
commit after Task 4.

**Goal:** Ship `add <path>`, fix the two defects the M2 live run exposed, and make `plan`'s output
tell the whole truth — the excluded and ignored files it currently computes and throws away, and the
secret warnings it currently emits with no test behind them.

**Architecture:** No new modules. M3 is one new command in `cli.py`, one new optional argument on
`plan.create_sync_plan`, and four corrections inside existing functions. `add` reuses the sync path
rather than growing a second apply: it stages one file into the source folder, then runs the same
plan-confirm-apply cycle `sync` runs, with the named file's proposal pre-accepted so the run does not
stop for review of the file the user just named.

**Tech Stack:** Python 3.9, standard library only, `unittest`. No network in any M3 test.

**Spec:** [design_artefact-sync.md](design_artefact-sync.md). Its supporting evidence, with
`file:line` citations into the prior art, is
[extraction-analysis.md](../history/extraction-analysis.md). The two defects Tasks 1 and 2 fix were
found by the M2 live run and are recorded in [m2-acceptance.md](m2-acceptance.md) under "What the run
found". M1's and M2's records, including the deviations this plan inherits, are
[plan_artefact-sync-m1.md](plan_artefact-sync-m1.md) and
[plan_artefact-sync-m2.md](plan_artefact-sync-m2.md).

---

## What M3 actually is

The design's ladder line reads "M3: `add`, secret warnings, SVG validator, plan output." Three of
those four are partly or wholly built already, because M1 over-delivered against its own task list.
Read the ladder line as a list of surfaces to *finish*, not to start.

| Ladder item | State at the end of M2 | M3's work |
|---|---|---|
| `add <path>` | Parsed by `cli.parse_args`, then `_dispatch` raises `"add command is not available yet"` | Task 5, wholly new |
| Secret warnings | `plan._SECRET_RULES` and `plan._PRIVATE_NAME` exist and run on every entry. Zero tests. The filename heuristic misses `Client Presentation.pdf`, `Internal Notes.html` and `q1-internal-review.md` — the three shapes a real folder actually holds | Task 3: a public seam, eight tests, and a heuristic that matches words wherever they appear |
| SVG validator | `scan.validate_svg` and `plan._svg_blocks` are built, and `tests/test_svg.py` covers the validator with 13 cases | Task 4 covers the one untested link: that a dirty SVG reaches the `BLOCKED` group with its line number. `test_a_dirty_svg_blocks_the_whole_run` asserts only exit 3, which an unlisted source produces on its own, so it passes with `_svg_blocks` deleted |
| Plan output | Grouping, full URLs, human sizes, diffs and the 10 MB size warning all ship, tested against a hand-built `SyncPlan` | Task 4: print the excluded and ignored counts the planner already computes and discards, order warnings deterministically, and say what an external reference does |

Plus the two defects the M2 live run found, which the M2 plan scoped to M3 by name: Tasks 1 and 2.

---

## Corrections to the design this plan applies

Each is a defect found by reading M1/M2 code against the design, or by the M2 live run. Each is
applied by a task.

| # | What the design or the code says | What M3 does | Why |
|---|---|---|---|
| M3-a | Invariant 4: "orphans are never deleted", printed as `in repo, in no manifest, left alone` | Subtract this run's `delete` destinations from the orphan scan | `plan.create_sync_plan` computes orphans as `scan_published_tree - expected`, and `expected` omits the destinations already queued for deletion. So the run prints the invariant-4 promise about a file it is deleting in the same breath. Found live at [m2-acceptance.md](m2-acceptance.md) row 10 |
| M3-b | `propose` groups root-level sources into one collection | Name that collection `general` / "General" | `propose._source_group` returns `""` for a root-level file, so the label falls through to `sources[0].stem` and the collection is named after whichever file sorts first. Found live at row 5, which named a four-file collection `probe-curve` |
| M3-c | "Secret-shape regexes and filename heuristics (`prompts/`, `draft`, `internal`, `client`) surface as warnings" | Match those words at any word boundary in the path | The shipped regex requires the word at the start of a path component *and* a `/`, `-`, `_` or `.` immediately after it. `Client Presentation.pdf` (space), `Internal Notes.html` (space) and `q1-internal-review.md` (mid-name) all pass silently. A heuristic that misses the common spellings is worse than none, because the clean plan output implies it looked |
| M3-d | Closed allowlist has three distinct outcomes: unsupported "summarised by suffix and excluded", ignored "excluded, counted", unlisted blocks | Print an `EXCLUDED` block | `create_sync_plan` binds the ignore counts to `_ignore_counts` and never reads `inventory.excluded` at all, so two of the three outcomes are invisible. A user whose file silently did not publish has nothing in the output to read |
| M3-e | `add <path>` "copies the file into the source folder ... proposes one entry, syncs that entry" | The named source's proposal does not block; every other unlisted source still does | Without this, `add` cannot apply anything on the run that introduces the file, which makes it `cp` plus `plan` and not worth a verb. Nothing becomes public: `publish` still lists every new URL and confirms |
| M3-f | `add` "syncs that one entry" | `add` recomputes and applies the whole tree, which is a superset of that entry | `manifest.json` and the catalogue change on every add, and both are functions of every entry, so a one-entry apply is not definable. D7 already settles the general case: the desired tree is a pure function of source plus manifest, so recomputing is a no-op wherever `sync` has already run. A second, narrower apply path would be the only thing a literal reading buys |

---

## Implementation Tasks

### Task 1: the orphan warning stops naming files this run deletes

Subtracted this run's deletion destinations from the orphan scan in `plan.create_sync_plan`, so design invariant 4's promise ("left alone") is never printed about a file being deleted in the same breath. Two tests in `tests/test_plan.py::OrphanNoteTests` pin both the fix and the guard.

### Task 2: a root-level collection gets a neutral name

Added `propose.ROOT_COLLECTION_LABEL = "General"` so sources at the source root get a stable collection name instead of one derived from whichever file sorts first. Two tests in `tests/test_propose.py::RootCollectionTests`.

### Task 3: the secret and private-name scan gets a seam, a fix, and tests

Exposed `plan.source_warnings(source, text)` as a public seam, replaced the component-prefix regex with a word-boundary match (`_PRIVATE_WORD`), and added `plan.TEXT_SUFFIXES` and `plan.external_note`. Nine tests in `tests/test_secrets.py` cover filename heuristics, secret shapes, and integration with the plan output.

### Task 4: plan output — excluded files, ordered warnings, and a blocked SVG that names its line

Extended `SyncPlan` with `excluded` and `ignored` fields (defaulted for backwards compatibility), added an `EXCLUDED` block to `format_plan`, sorted warnings by `(kind, where)`, and wired `validate.py` to use `plan.external_note`. Strengthened the dirty-SVG test to assert the line number reaches the `BLOCKED` section. Eight tests across `tests/test_plan.py` and `tests/test_m1_end_to_end.py`.

### Task 5: `add <path>`

Implemented `cli.command_add` which stages one file into the source folder and applies the recomputed tree. Added `plan.create_sync_plan(..., accepted=())` so the named source's proposal does not block. Factored `cli._apply_or_report` as the shared tail for both `sync` and `add`. Eight tests in `tests/test_add.py` cover outside-file publish, collision refusal, inside-file no-copy, extension and ignore-rule refusal, other-unlisted-still-blocks, confirmation decline, and directory refusal.

### Task 6: M3 acceptance — the add loop end to end, and SKILL.md

Wrote `tests/test_m3_end_to_end.py` proving the full add-then-delete-then-converge loop and the `EXCLUDED` output. Updated `SKILL.md` with the `add` command and a `## Warnings` section.

---

## Critical Files — Summary

| Path | M3's change |
|---|---|
| `artefact_sync/plan.py` | Orphan fix, `source_warnings`, `external_note`, `accepted`, `excluded`/`ignored`, `EXCLUDED` block, sorted warnings |
| `artefact_sync/propose.py` | `ROOT_COLLECTION_LABEL` |
| `artefact_sync/validate.py` | External notes share `plan.external_note`'s wording |
| `artefact_sync/cli.py` | `command_add`, `_source_relative`, `_apply_or_report` |
| `SKILL.md` | `add` and a warnings section |

---

## Deviations from this plan

Recorded because the plan was written before the code existed, and a plan that hides where it was
wrong is worth less on the next milestone.

Plan defects found and corrected during implementation:

- Task 3 Step 2 predicted every new test would error because `source_warnings` did not exist. Eight
  did. The integration test does not call that seam directly, so it reached the existing private-name
  scan and failed its assertion on the old `filename looks private` wording instead.
- Task 3 combined the AWS-key and private-key failures in one test method. They are distinct secret
  shapes, so implementation split them into distinct methods. Task 3 therefore ended at **209**
  tests, not 208.
- Task 4 Step 2 predicted the strengthened SVG test would fail before implementation. It passed:
  `_svg_blocks` already put `d/bad.svg:2` and `script element` in the blocked section. The old test
  was weak, but the link it failed to prove was working.
- Task 4 combined unsupported files, ignored files and their total in one test, and combined warning
  kind order with within-kind path order in another. Those are distinct failures, so implementation
  gave each its own method. Task 4 added eight methods and ended at **217** tests, not 213.
- Task 5 Step 2 predicted all eight tests would fail with exit 1 and `add command is not available
  yet`. Seven errored with `SystemExit: 2` because their `--yes` argument was rejected by the parser
  before dispatch. The confirmation test reached dispatch and failed because the unavailable-command
  message was written to stderr while that test captured only stdout.
- Task 5 added eight methods to the real 217-test baseline and ended at **225** tests, not 221.
- Task 6 added two methods and ended at **227** tests on both interpreters, not 223.
- Commit `2b2960e` is an extra driver-cleanup commit beyond the task commit list. It removed the
  unused `kinds()` helper that Task 3's test snippet carried into `tests/test_secrets.py`.

No correction to [design_artefact-sync.md](design_artefact-sync.md) was required by Tasks 1-6.

---

## Changelog

- 2026-08-25 — **Compacted post-implementation.** Removed step-by-step tasks, file-by-file diffs, code snippets, and verification commands now that the feature has shipped. Preserved Goal, Architecture, Corrections, Critical Files summary, and Deviations. Original plan recoverable via git history.
