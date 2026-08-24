# artefact-sync M3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

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
[extraction-analysis.md](../research/extraction-analysis.md). The two defects Tasks 1 and 2 fix were
found by the M2 live run and are recorded in [m2-acceptance.md](m2-acceptance.md) under "What the run
found". M1's and M2's records, including the deviations this plan inherits, are
[plan_artefact-sync-m1.md](plan_artefact-sync-m1.md) and
[plan_artefact-sync-m2.md](plan_artefact-sync-m2.md).

## Global Constraints

Every task's requirements implicitly include this section. The first nine are carried unchanged from
M2.

- **Python 3.9.** The tool must run under stock macOS `/usr/bin/python3` (3.9.6). Every module
  starts with `from __future__ import annotations` so `X | None` annotations parse on 3.9.
- **Standard library only.** No third-party import in the shipped package or in its tests, ever.
  `tests/test_stdlib_only.py` already allows every module M3 needs (`re`, `shutil`, `pathlib`);
  do not widen `ALLOWED`.
- **Test command:** `python3 -m unittest discover -s tests -t . -v`. Never pytest. Run it under
  **both** `python3` (3.13) and `/usr/bin/python3` (3.9.6) before every commit.
- **The M2 baseline is 195 tests, all passing on both interpreters.** No task may leave that number
  lower.
- **British spelling** in every user-facing string, path and identifier: `artefacts`, `catalogue`.
- **No emoji** in any output. `tests/test_plan.py::test_no_emoji_anywhere_in_the_output` enforces it
  for `format_plan`; keep it passing.
- **Repo root is the skill directory.** This repo is cloned to `~/.claude/skills/artefact-sync/`.
- **Never write to `/Users/keli/dev/github-kevinlin/kevinlin.github.io`.** It is a live site with 57
  published URLs. `git -C <that repo> status --short` must stay empty.
- **Exit codes:** `0` success, `1` error, `3` blocked and needs a human decision.
- **No network in the unit suite.** M3 adds no networked code path. Every test runs offline; `init`
  in a fixture repo has no `origin`, so `provider.derive_base_url` returns `None` and nothing is
  fetched.
- **Every test count in this plan is a prediction.** M2's own deviations record two cases where a
  stated count was satisfied by contorting the code instead of correcting the number. If your test
  count differs from the prediction, the number here is wrong. Fix the number in "Deviations from
  this plan"; never merge two distinct failures into one `subTest` loop, and never build a name by
  string concatenation, to hit a figure written before the code existed.

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

Record any further corrections in "Deviations from this plan" at the bottom, and apply them to
[design_artefact-sync.md](design_artefact-sync.md), exactly as M1 and M2 did.

---

## File Structure

```
artefact-sync/
  SKILL.md                        + add section, + warnings section, - "reserved for M3"
  artefact_sync/
    plan.py                       + accepted argument, + excluded/ignored on SyncPlan,
                                  + source_warnings, + external_note, orphan fix, format fix
    propose.py                    + ROOT_COLLECTION_LABEL
    validate.py                   external notes go through plan.external_note
    cli.py                        + command_add, + _source_relative, + _apply_or_report
  tests/
    test_plan.py                  + OrphanNoteTests, + ExcludedBlockTests, + warning order
    test_propose.py               + RootCollectionTests
    test_secrets.py     NEW       the secret and private-name scan
    test_add.py         NEW       the add command
    test_m3_end_to_end.py NEW     the add loop against a fixture repo
    test_m1_end_to_end.py         dirty-SVG test strengthened to name the line
  docs/specs/
    plan_artefact-sync-m3.md      this file: status line and deviations, at the end
```

Dependency direction is unchanged. `add` adds no edge: `cli.py` already imports `plan`, `apply` and
`manifest`.

---

## Implementation Tasks

### Task 1: the orphan warning stops naming files this run deletes

**Files:**
- Modify: `artefact_sync/plan.py:243-250` (the orphan scan inside `create_sync_plan`)
- Test: `tests/test_plan.py`

**Interfaces:**
- Consumes: `plan.create_sync_plan`, `plan.DELETION_KINDS`, `cli.main`, `cli.resolve_context`,
  `cli.parse_args`, `manifest.load_manifest`, `tests.helpers.make_repo`,
  `tests.helpers.make_source_tree`.
- Produces: nothing new. Behaviour change only: `SyncPlan.notes` no longer carries an `orphan` note
  for a destination that appears in `SyncPlan.changes` with kind `delete`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_plan.py`. Add `from artefact_sync import cli, manifest as manifest_module` to
the imports at the top of the file (it currently imports only `plan`, `config`, `errors`,
`manifest.Manifest` and the helpers).

```python
class OrphanNoteTests(unittest.TestCase):
    """Design invariant 4 promises orphans are never deleted. Do not print it about a deletion."""

    def _synced_repo(self, tmp: Path, files: dict) -> tuple[Path, Path, Path]:
        root = Path(tmp)
        repo = make_repo(root, {"README.md": b"x\n"})
        source = make_source_tree(root, files)
        pointer = root / "pointer.json"
        cli.main(["init", "--pointer", str(pointer),
                  "--repo", str(repo), "--source", str(source)])
        cli.main(["plan", "--pointer", str(pointer)])            # proposes, exits 3
        cli.main(["sync", "--pointer", str(pointer), "--yes"])   # publishes
        return repo, source, pointer

    def _replan(self, pointer: Path) -> p.SyncPlan:
        context = cli.resolve_context(cli.parse_args(["plan", "--pointer", str(pointer)]))
        return p.create_sync_plan(context, manifest_module.load_manifest(context.artefacts_root))

    def test_a_file_this_run_deletes_is_not_also_called_an_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = self._synced_repo(tmp, {"keep.png": b"keep"})
            (source / "keep.png").unlink()
            sync_plan = self._replan(pointer)
        deleted = [change.destination.as_posix() for change in sync_plan.changes
                   if change.kind in p.DELETION_KINDS]
        self.assertEqual(["keep.png"], deleted)
        self.assertEqual(
            [],
            [note for note in sync_plan.notes
             if note.kind == "orphan" and "keep.png" in note.where],
        )

    def test_a_genuinely_unmanaged_file_is_still_warned_about(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, pointer = self._synced_repo(tmp, {"keep.png": b"keep"})
            (repo / "artefacts" / "redirect.html").write_bytes(b"<html></html>\n")
            sync_plan = self._replan(pointer)
        self.assertEqual(
            ["artefacts/redirect.html"],
            [note.where for note in sync_plan.notes if note.kind == "orphan"],
        )
```

- [ ] **Step 2: Run the tests to verify the first one fails**

Run: `python3 -m unittest tests.test_plan.OrphanNoteTests -v`
Expected: `test_a_file_this_run_deletes_is_not_also_called_an_orphan` FAILS on the second assertion,
with one `Note(kind='orphan', where='artefacts/keep.png', ...)` in the list.
`test_a_genuinely_unmanaged_file_is_still_warned_about` PASSES already — it is the guard that Step 3
does not silence the whole warning.

- [ ] **Step 3: Subtract this run's deletions from the orphan scan**

In `artefact_sync/plan.py`, inside `create_sync_plan`, replace:

```python
    notes = _source_notes(context, next_manifest, desired_files)
    expected = {
        *desired_files,
        *next_manifest.protected_files,
        *(PurePosixPath(name) for name in manifest_module.CONTROL_FILES),
    }
```

with:

```python
    notes = _source_notes(context, next_manifest, desired_files)
    # A destination queued for deletion is managed, not unmanaged. Warning that it is being
    # "left alone" would print design invariant 4 about the one file this run removes.
    expected = {
        *desired_files,
        *next_manifest.protected_files,
        *(change.destination for change in changes if change.kind in DELETION_KINDS),
        *(PurePosixPath(name) for name in manifest_module.CONTROL_FILES),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_plan -v` then
`/usr/bin/python3 -m unittest discover -s tests -t . 2>&1 | tail -3`
Expected: both new tests PASS; whole suite OK at 197 tests.

- [ ] **Step 5: Commit**

```bash
git add artefact_sync/plan.py tests/test_plan.py
git commit -m "fix(plan): stop calling a file this run deletes an orphan"
```

---

### Task 2: a root-level collection gets a neutral name

**Files:**
- Modify: `artefact_sync/propose.py:11` (constants) and `:150` (the label fallback)
- Test: `tests/test_propose.py`

**Interfaces:**
- Consumes: `propose.propose_manifest_additions`, `manifest.Manifest`, `config.site_from_dict`,
  `tests.helpers.make_source_tree`.
- Produces: `propose.ROOT_COLLECTION_LABEL = "General"`. Sources at the source root propose
  collection id `general`, title `General`, section `Artefacts`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_propose.py`:

```python
SITE = site_from_dict({"base_url": "https://x.example/artefacts/"})


class RootCollectionTests(unittest.TestCase):
    def _propose(self, files: dict) -> Manifest:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), files)
            empty = Manifest(1, SITE, (), (), (), ())
            return propose.propose_manifest_additions(
                empty,
                tuple(PurePosixPath(name) for name in sorted(files)),
                {},
                source,
            )

    def test_root_level_sources_are_not_named_after_their_first_file(self) -> None:
        result = self._propose({"curve.png": b"1", "note.md": b"# Note\n"})
        self.assertEqual(("general",), tuple(c.id for c in result.collections))
        self.assertEqual(("General",), tuple(c.title for c in result.collections))
        self.assertEqual({"general"}, {entry.collection for entry in result.entries})

    def test_a_subdirectory_still_names_its_own_collection(self) -> None:
        result = self._propose({"talk/curve.png": b"1"})
        self.assertEqual(("talk",), tuple(c.id for c in result.collections))
        self.assertEqual(("Talk",), tuple(c.title for c in result.collections))
```

- [ ] **Step 2: Run the tests to verify the first one fails**

Run: `python3 -m unittest tests.test_propose.RootCollectionTests -v`
Expected: `test_root_level_sources_are_not_named_after_their_first_file` FAILS with
`('curve',) != ('general',)`. The subdirectory test PASSES — it pins the behaviour that must not
change.

- [ ] **Step 3: Name the root group**

In `artefact_sync/propose.py`, add the constant beside `DEFAULT_SECTION`:

```python
DEFAULT_SECTION = "Artefacts"
DEFAULT_DESCRIPTION = None
# Root-level sources have no directory to name their collection after. Naming it for whichever
# file sorts first is arbitrary, and the arbitrary run is the first one a new user sees.
ROOT_COLLECTION_LABEL = "General"
```

and in `propose_manifest_additions`, replace:

```python
            label = group or sources[0].stem
```

with:

```python
            label = group or ROOT_COLLECTION_LABEL
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_propose -v` then the whole suite on both interpreters.
Expected: both new tests PASS, suite OK at 199 tests.

- [ ] **Step 5: Commit**

```bash
git add artefact_sync/propose.py tests/test_propose.py
git commit -m "fix(propose): name a root-level collection General, not after its first file"
```

---

### Task 3: the secret and private-name scan gets a seam, a fix, and tests

**Files:**
- Modify: `artefact_sync/plan.py:99-135` (`_SECRET_RULES`, `_PRIVATE_NAME`, `_source_notes`)
- Test: `tests/test_secrets.py` (create)

**Interfaces:**
- Consumes: `plan.Note`, `render.external_references`.
- Produces:
  - `plan.TEXT_SUFFIXES: frozenset[str]` — `{".html", ".md", ".svg"}`, the suffixes the scan reads.
  - `plan.source_warnings(source: PurePosixPath, text: str | None) -> list[Note]` — filename
    heuristics plus secret shapes for one source. `text` is `None` for a binary source or one that
    would not decode, and then only the filename check runs.
  - `plan._PRIVATE_WORD` replaces `plan._PRIVATE_NAME` (private, named here so nobody imports the
    old one).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_secrets.py`:

```python
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePosixPath

from artefact_sync import cli, plan as p
from tests.helpers import make_repo, make_source_tree


def kinds(notes) -> list:
    return [(note.kind, note.where, note.detail) for note in notes]


class FilenameHeuristicTests(unittest.TestCase):
    """The requirement names the words prompts, draft, internal and client."""

    def test_a_spaced_client_filename_warns(self) -> None:
        notes = p.source_warnings(PurePosixPath("Client Presentation.pdf"), None)
        self.assertEqual(1, len(notes))
        self.assertEqual("secret", notes[0].kind)
        self.assertIn("client", notes[0].detail)

    def test_a_word_in_the_middle_of_a_name_warns(self) -> None:
        self.assertEqual(1, len(p.source_warnings(PurePosixPath("q1-internal-review.md"), "")))

    def test_a_nested_draft_warns(self) -> None:
        self.assertEqual(1, len(p.source_warnings(PurePosixPath("talk/old-drafts.md"), "")))

    def test_a_word_that_merely_starts_the_same_does_not_warn(self) -> None:
        self.assertEqual([], p.source_warnings(PurePosixPath("clientele-map.png"), None))

    def test_an_ordinary_name_does_not_warn(self) -> None:
        self.assertEqual([], p.source_warnings(PurePosixPath("talk/adoption-curve.png"), None))


class SecretShapeTests(unittest.TestCase):
    def test_an_api_key_warns_with_its_line_number(self) -> None:
        text = "intro\nkey = sk-abcdefghijklmnopqrstuvwx\n"
        notes = p.source_warnings(PurePosixPath("talk/cost-model.html"), text)
        self.assertEqual(1, len(notes))
        self.assertEqual("talk/cost-model.html:2", notes[0].where)
        self.assertIn("API key", notes[0].detail)

    def test_an_aws_key_and_a_private_key_both_warn(self) -> None:
        text = "AKIAIOSFODNN7EXAMPLE\n-----BEGIN RSA PRIVATE KEY-----\n"
        self.assertEqual(2, len(p.source_warnings(PurePosixPath("a.md"), text)))

    def test_a_binary_source_is_never_read_for_secrets(self) -> None:
        self.assertEqual([], p.source_warnings(PurePosixPath("curve.png"), None))


class PlanIntegrationTests(unittest.TestCase):
    def test_a_secret_in_a_source_reaches_the_plan_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {
                "internal-notes.md": b"# Notes\n\nkey = sk-abcdefghijklmnopqrstuvwx\n",
            })
            pointer = root / "pointer.json"
            cli.main(["init", "--pointer", str(pointer),
                      "--repo", str(repo), "--source", str(source)])
            context = cli.resolve_context(cli.parse_args(["plan", "--pointer", str(pointer)]))
            from artefact_sync import manifest as manifest_module
            sync_plan = p.create_sync_plan(
                context, manifest_module.load_manifest(context.artefacts_root))
            text = p.format_plan(sync_plan)
        self.assertIn("internal-notes.md:3", text)
        self.assertIn("API key", text)
        self.assertIn('filename contains "internal"', text)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_secrets -v`
Expected: every test errors with `AttributeError: module 'artefact_sync.plan' has no attribute
'source_warnings'`.

- [ ] **Step 3: Add the seam and widen the heuristic**

In `artefact_sync/plan.py`, replace the `_PRIVATE_NAME` definition and `_source_notes` with:

```python
# Word-boundary, not component-prefix: the shipped rule missed "Client Presentation.pdf",
# "Internal Notes.html" and "q1-internal-review.md", which are the shapes a real folder holds.
_PRIVATE_WORD = re.compile(r"(?<![a-z0-9])(?:prompts?|drafts?|internal|client)(?![a-z0-9])", re.I)

TEXT_SUFFIXES = frozenset({".html", ".md", ".svg"})


def external_note(where: str, url: str) -> Note:
    return Note("external", where, f"loads {url} at runtime")


def source_warnings(source: PurePosixPath, text: str | None) -> list[Note]:
    """Filename heuristics plus secret shapes for one source. `text` is None for binary sources."""
    label = source.as_posix()
    notes = []
    match = _PRIVATE_WORD.search(label)
    if match is not None:
        notes.append(Note("secret", label, f'filename contains "{match.group(0).lower()}"'))
    if text is None:
        return notes
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern, detail in _SECRET_RULES:
            if pattern.search(line):
                notes.append(Note("secret", f"{label}:{number}", detail))
    return notes


def _source_notes(context: Context, manifest: Manifest, desired_files) -> list[Note]:
    notes = []
    for entry in manifest.entries:
        text = None
        if entry.source.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = (context.source_root / entry.source.as_posix()).read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                text = None
        notes.extend(source_warnings(entry.source, text))
        if entry.source.suffix.lower() != ".html":
            continue
        rendered = desired_files.get(entry.destination)
        if rendered is None:
            continue
        try:
            document = rendered.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for number, url in render.external_references(document):
            notes.append(external_note(f"{entry.source}:{number}", url))
    return notes
```

`external_note` is defined here rather than in Task 4 because both call sites want one wording and
this is the file that owns `Note`. Task 4 wires `validate.py` to it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_secrets -v` then the whole suite on both interpreters.
Expected: nine new tests PASS, suite OK at 208 tests. If any existing test asserted the bare-URL
external detail it fails here — no test does today, so a failure means Step 3 changed something else.

- [ ] **Step 5: Commit**

```bash
git add artefact_sync/plan.py tests/test_secrets.py
git commit -m "feat(plan): test the secret scan and match private words anywhere in a path"
```

---

### Task 4: plan output — excluded files, ordered warnings, and a blocked SVG that names its line

**Files:**
- Modify: `artefact_sync/plan.py` (`SyncPlan`, `create_sync_plan`, `format_plan`)
- Modify: `artefact_sync/validate.py:107-108` (external notes go through `plan.external_note`)
- Test: `tests/test_plan.py`, `tests/test_m1_end_to_end.py`

**Interfaces:**
- Consumes: `plan.Note`, `plan.external_note` (Task 3), `scan.SourceInventory.excluded`,
  `scan.apply_source_ignores`.
- Produces:
  - `SyncPlan` gains two fields, both defaulted so every existing construction keeps working:
    `excluded: tuple[tuple[str, int], ...] = ()` — `(suffix_label, count)` per unsupported suffix,
    and `ignored: tuple[tuple[str, int], ...] = ()` — `(rule, count)` per ignore rule that matched
    at least one file.
  - `format_plan` gains an `EXCLUDED` block, printed after the change groups and before `WARNINGS`,
    and sorts warnings by `(kind, where)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_plan.py`:

```python
class ExcludedBlockTests(unittest.TestCase):
    def test_unsupported_and_ignored_files_are_summarised(self) -> None:
        text = p.format_plan(
            p.SyncPlan(
                changes=(), notes=(), blocked=(), desired_files={}, next_manifest=None,
                excluded=((".psd", 1), (".mp4", 2)),
                ignored=(("drafts/", 3),),
            )
        )
        self.assertIn("EXCLUDED (6)", text)
        self.assertIn(".psd", text)
        self.assertIn("1 file, unsupported type", text)
        self.assertIn("2 files, unsupported type", text)
        self.assertIn("drafts/", text)
        self.assertIn("3 files, matched an ignored source rule", text)

    def test_nothing_excluded_prints_no_heading(self) -> None:
        text = p.format_plan(
            p.SyncPlan(changes=(), notes=(), blocked=(), desired_files={}, next_manifest=None)
        )
        self.assertNotIn("EXCLUDED", text)

    def test_excluded_sits_between_the_change_groups_and_the_warnings(self) -> None:
        text = p.format_plan(
            p.SyncPlan(
                changes=(p.Change("delete", PurePosixPath("old.pdf"), None, None,
                                  "https://x.example/artefacts/old.pdf", None),),
                notes=(p.Note("orphan", "artefacts/redirect.html", "kept"),),
                blocked=(), desired_files={}, next_manifest=None,
                excluded=((".psd", 1),), ignored=(),
            )
        )
        self.assertLess(text.index("WILL START 404-ING"), text.index("EXCLUDED"))
        self.assertLess(text.index("EXCLUDED"), text.index("WARNINGS"))

    def test_a_real_scan_reports_its_own_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {
                "keep.png": b"1", "notes.psd": b"binary", "drafts/wip.md": b"# wip\n",
            })
            pointer = root / "pointer.json"
            cli.main(["init", "--pointer", str(pointer),
                      "--repo", str(repo), "--source", str(source)])
            context = cli.resolve_context(cli.parse_args(["plan", "--pointer", str(pointer)]))
            sync_plan = p.create_sync_plan(
                context, manifest_module.load_manifest(context.artefacts_root))
        self.assertIn((".psd", 1), sync_plan.excluded)
        self.assertIn(("drafts/", 1), sync_plan.ignored)
        self.assertNotIn(("*.local.*", 0), sync_plan.ignored)


class WarningOrderTests(unittest.TestCase):
    def test_warnings_are_grouped_by_kind_and_ordered_within_a_kind(self) -> None:
        text = p.format_plan(
            p.SyncPlan(
                changes=(),
                notes=(
                    p.Note("secret", "z.md:1", "looks like an API key"),
                    p.Note("orphan", "artefacts/b.html", "in repo, in no manifest, left alone"),
                    p.Note("external", "a.html:9", "loads https://unpkg.example/x.js at runtime"),
                    p.Note("orphan", "artefacts/a.html", "in repo, in no manifest, left alone"),
                ),
                blocked=(), desired_files={}, next_manifest=None,
            )
        )
        rows = [line.split()[0] for line in text.splitlines() if line.startswith("  ")]
        self.assertEqual(["external", "orphan", "orphan", "secret"], rows)
        self.assertLess(text.index("artefacts/a.html"), text.index("artefacts/b.html"))
```

And replace `test_a_dirty_svg_blocks_the_whole_run` in `tests/test_m1_end_to_end.py`, which passes
today with `plan._svg_blocks` deleted because an unlisted source blocks on its own:

```python
    def test_a_dirty_svg_blocks_the_run_and_names_the_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"d/bad.svg": b"<svg>\n<script/>\n</svg>\n"})
            pointer = root / "pointer.json"
            cli.main(["init", "--pointer", str(pointer),
                      "--repo", str(repo), "--source", str(source)])
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["plan", "--pointer", str(pointer)])
                # The first run also blocks for the unlisted source, and writes its proposal.
                # The second run has the entry, so only the SVG itself can still block it.
                second = cli.main(["plan", "--pointer", str(pointer)])
            text = buffer.getvalue()
        self.assertEqual(cli.EXIT_BLOCKED, code)
        self.assertEqual(cli.EXIT_BLOCKED, second)
        blocked = text[text.index("BLOCKED"):]
        self.assertIn("d/bad.svg:2", blocked)
        self.assertIn("script element", blocked)
```

Add `import contextlib` and `import io` to that file's imports.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_plan.ExcludedBlockTests tests.test_plan.WarningOrderTests tests.test_m1_end_to_end -v`
Expected: the `SyncPlan(...)` constructions raise `TypeError: __init__() got an unexpected keyword
argument 'excluded'`; `WarningOrderTests` FAILS with the notes in insertion order; the SVG test
FAILS on `d/bad.svg:2` not being in the blocked section.

- [ ] **Step 3: Carry the counts through and format them**

In `artefact_sync/plan.py`, extend `SyncPlan`:

```python
@dataclass(frozen=True)
class SyncPlan:
    changes: tuple[Change, ...]
    notes: tuple[Note, ...]
    blocked: tuple[Blocked, ...]
    desired_files: dict[PurePosixPath, bytes]
    next_manifest: Manifest | None
    # Two of the closed allowlist's three outcomes. Defaulted so M1/M2 constructions still work.
    excluded: tuple[tuple[str, int], ...] = ()
    ignored: tuple[tuple[str, int], ...] = ()
```

In `create_sync_plan`, keep the ignore counts instead of dropping them:

```python
    inventory, ignore_counts = scan.apply_source_ignores(
        scan.scan_source(context.source_root, context.repo_root), declared.ignored_sources
    )
```

and pass both through in the return:

```python
    return SyncPlan(
        changes=tuple(changes),
        notes=tuple(notes),
        blocked=tuple(blocked),
        desired_files=desired_files,
        next_manifest=next_manifest,
        excluded=inventory.excluded,
        ignored=tuple((rule, count) for rule, count in ignore_counts if count),
    )
```

Then in `format_plan`, add the block and sort the warnings. Replace the `if plan.notes:` stanza with:

```python
    excluded_rows = [(label, count, "unsupported type") for label, count in plan.excluded]
    excluded_rows += [
        (rule, count, "matched an ignored source rule") for rule, count in plan.ignored
    ]
    if excluded_rows:
        lines = [f"EXCLUDED ({sum(count for _, count, _ in excluded_rows)})"]
        for label, count, reason in excluded_rows:
            files = "1 file" if count == 1 else f"{count} files"
            lines.append(f"  {label:<14} {files}, {reason}")
        blocks.append("\n".join(lines))

    if plan.notes:
        lines = [f"WARNINGS ({len(plan.notes)})"]
        for note in sorted(plan.notes, key=lambda item: (item.kind, item.where)):
            lines.append(f"  {note.kind:<9} {note.where}    {note.detail}")
        blocks.append("\n".join(lines))
```

In `artefact_sync/validate.py`, use the shared wording for external notes. Replace:

```python
        for line, url in render.external_references(text):
            notes.append(plan_module.Note("external", f"artefacts/{relative}:{line}", url))
```

with:

```python
        for line, url in render.external_references(text):
            notes.append(plan_module.external_note(f"artefacts/{relative}:{line}", url))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -t . -v 2>&1 | tail -5` and the same under
`/usr/bin/python3`.
Expected: OK at 213 tests. `test_no_emoji_anywhere_in_the_output` still passes — every character
added here is ASCII.

- [ ] **Step 5: Commit**

```bash
git add artefact_sync/plan.py artefact_sync/validate.py tests/test_plan.py tests/test_m1_end_to_end.py
git commit -m "feat(plan): report excluded and ignored files, order warnings, prove SVG blocks"
```

---

### Task 5: `add <path>`

**Files:**
- Modify: `artefact_sync/plan.py` (`create_sync_plan` gains `accepted`)
- Modify: `artefact_sync/cli.py` (`parse_args`, `command_sync`, `_dispatch`, plus the new code)
- Test: `tests/test_add.py` (create)

**Interfaces:**
- Consumes: `manifest.APPROVED_EXTENSIONS`, `manifest.is_ignored`, `plan.create_sync_plan`,
  `plan.format_plan`, `apply_module.apply_plan`, `cli._command_state`,
  `cli._write_proposed_manifest`, `config.Context`.
- Produces:
  - `plan.create_sync_plan(context, manifest, accepted: tuple[PurePosixPath, ...] = ())` — sources in
    `accepted` do not raise the "approved source has no manifest entry" block. Every other unlisted
    source still does. Nothing else about the plan changes.
  - `cli._source_relative(context, given: Path) -> PurePosixPath` — where `given` will live relative
    to the source root: its existing relative path when it is already inside, otherwise its bare
    filename.
  - `cli._apply_or_report(args, context, sync_plan, verb: str) -> int` — the print, block, confirm,
    apply tail shared by `sync` and `add`.
  - `cli.command_add(args) -> int` — stages the file, then applies the recomputed tree. That tree is
    a superset of the named entry, per correction M3-f.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_add.py`:

```python
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from artefact_sync import cli
from tests.helpers import make_repo, make_source_tree


class AddTests(unittest.TestCase):
    def _fixture(self, tmp: str, files: dict | None = None) -> tuple[Path, Path, Path]:
        root = Path(tmp)
        repo = make_repo(root, {"README.md": b"x\n"})
        source = make_source_tree(root, files or {})
        pointer = root / "pointer.json"
        cli.main(["init", "--pointer", str(pointer),
                  "--repo", str(repo), "--source", str(source)])
        return repo, source, pointer

    def _entries(self, repo: Path) -> list:
        return json.loads((repo / "artefacts" / "manifest.json").read_text())["entries"]

    def _run(self, argv: list) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_an_outside_file_is_copied_and_published_in_one_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, source, pointer = self._fixture(tmp)
            elsewhere = Path(tmp) / "elsewhere"
            elsewhere.mkdir()
            (elsewhere / "Adoption Curve.png").write_bytes(b"PNGDATA")
            code, text = self._run(["add", str(elsewhere / "Adoption Curve.png"),
                                    "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_OK, code, text)
            self.assertEqual(b"PNGDATA", (source / "Adoption Curve.png").read_bytes())
            self.assertEqual(b"PNGDATA",
                             (repo / "artefacts" / "adoption-curve.png").read_bytes())
            entries = self._entries(repo)
        self.assertEqual(["Adoption Curve.png"], [entry["source"] for entry in entries])
        self.assertEqual("Adoption Curve", entries[0]["title"])
        self.assertNotIn("BLOCKED", text)

    def test_a_collision_in_the_source_folder_refuses_and_copies_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = self._fixture(tmp, {"curve.png": b"ORIGINAL"})
            elsewhere = Path(tmp) / "elsewhere"
            elsewhere.mkdir()
            (elsewhere / "curve.png").write_bytes(b"REPLACEMENT")
            code, text = self._run(["add", str(elsewhere / "curve.png"),
                                    "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_ERROR, code)
            self.assertEqual(b"ORIGINAL", (source / "curve.png").read_bytes())
        self.assertIn("already exists", text)

    def test_a_path_already_inside_the_source_folder_is_not_copied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, source, pointer = self._fixture(tmp, {"talk/curve.png": b"PNGDATA"})
            code, text = self._run(["add", str(source / "talk" / "curve.png"),
                                    "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_OK, code, text)
            self.assertFalse((source / "curve.png").exists())
            entries = self._entries(repo)
        self.assertEqual(["talk/curve.png"], [entry["source"] for entry in entries])
        self.assertEqual("talk/curve.png", entries[0]["destination"])

    def test_an_unapproved_extension_refuses_before_copying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = self._fixture(tmp)
            elsewhere = Path(tmp) / "notes.psd"
            elsewhere.write_bytes(b"binary")
            code, text = self._run(["add", str(elsewhere), "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_ERROR, code)
            self.assertFalse((source / "notes.psd").exists())
        self.assertIn(".psd", text)

    def test_a_name_matching_an_ignore_rule_refuses_before_copying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = self._fixture(tmp)
            elsewhere = Path(tmp) / "curve.local.png"
            elsewhere.write_bytes(b"PNGDATA")
            code, text = self._run(["add", str(elsewhere), "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_ERROR, code)
            self.assertFalse((source / "curve.local.png").exists())
        self.assertIn("ignored_sources", text)

    def test_another_unlisted_source_still_blocks_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, source, pointer = self._fixture(tmp, {"stranger.png": b"OTHER"})
            elsewhere = Path(tmp) / "curve.png"
            elsewhere.write_bytes(b"PNGDATA")
            code, text = self._run(["add", str(elsewhere), "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_BLOCKED, code)
            self.assertEqual(b"PNGDATA", (source / "curve.png").read_bytes())
            self.assertFalse((repo / "artefacts" / "curve.png").exists())
            sources = [entry["source"] for entry in self._entries(repo)]
        self.assertIn("stranger.png", text)
        self.assertEqual(["curve.png", "stranger.png"], sorted(sources))

    def test_declining_the_confirmation_applies_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, pointer = self._fixture(tmp)
            elsewhere = Path(tmp) / "curve.png"
            elsewhere.write_bytes(b"PNGDATA")
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer), unittest.mock.patch(
                "builtins.input", return_value="no"
            ):
                code = cli.main(["add", str(elsewhere), "--pointer", str(pointer)])
            self.assertEqual(cli.EXIT_ERROR, code)
            self.assertFalse((repo / "artefacts" / "curve.png").exists())
        self.assertIn("nothing was applied", buffer.getvalue())

    def test_a_directory_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = self._fixture(tmp)
            code, text = self._run(["add", str(source), "--pointer", str(pointer), "--yes"])
        self.assertEqual(cli.EXIT_ERROR, code)
        self.assertIn("not a regular file", text)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_add -v`
Expected: every test FAILS with exit code 1 and `add command is not available yet` in the output.

- [ ] **Step 3: Pre-accept the named source in the planner**

In `artefact_sync/plan.py`, change the signature and the one line that uses it:

```python
def create_sync_plan(
    context: Context, manifest: Manifest, accepted: tuple[PurePosixPath, ...] = ()
) -> SyncPlan:
```

```python
    # `accepted` holds sources the user named on the command line, so their proposal is not a
    # decision the run has to stop for. Every other unlisted source still blocks.
    blocked = [
        Blocked(source.as_posix(), "approved source has no manifest entry; proposal generated")
        for source in unlisted
        if source not in renames and source not in accepted
    ]
```

- [ ] **Step 4: Write `add`**

In `artefact_sync/cli.py`, factor the shared tail out of `command_sync` and add the command.
Replace `command_sync` with:

```python
def _apply_or_report(
    args: argparse.Namespace,
    context: config.Context,
    sync_plan: plan_module.SyncPlan,
    verb: str,
) -> int:
    print(plan_module.format_plan(sync_plan), end="")
    if sync_plan.blocked:
        _write_proposed_manifest(context, sync_plan)
        return EXIT_BLOCKED
    if not args.yes and input("Apply these changes? Type yes to continue: ") != "yes":
        print(f"{verb} cancelled; nothing was applied.")
        return EXIT_ERROR
    apply_module.apply_plan(context, sync_plan)
    return EXIT_OK


def command_sync(args: argparse.Namespace) -> int:
    context, current = _command_state(args)
    return _apply_or_report(args, context, plan_module.create_sync_plan(context, current), "sync")


def _source_relative(context: config.Context, given: Path) -> PurePosixPath:
    """Where `given` will live, relative to the source root."""
    resolved = given.resolve()
    root = context.source_root.resolve()
    if resolved.is_relative_to(root):
        return PurePosixPath(resolved.relative_to(root).as_posix())
    return PurePosixPath(resolved.name)


def command_add(args: argparse.Namespace) -> int:
    context, current = _command_state(args)
    given = args.path.expanduser()
    if given.is_symlink() or not given.is_file():
        raise ConfigError(f"not a regular file: {given}")
    if given.suffix.lower() not in manifest.APPROVED_EXTENSIONS:
        raise ConfigError(
            f"{given.suffix or given.name} is not an approved type; approved: "
            + " ".join(sorted(manifest.APPROVED_EXTENSIONS))
        )
    relative = _source_relative(context, given)
    if manifest.is_ignored(relative, current.ignored_sources):
        raise ConfigError(
            f"{relative.as_posix()} matches an ignored_sources rule and would never sync; "
            "rename it or edit ignored_sources in the manifest"
        )
    target = context.source_root / relative.as_posix()
    if target.resolve() != given.resolve():
        if target.exists() or target.is_symlink():
            raise ConfigError(
                f"{target} already exists; rename the file, or edit it in place and run sync"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(given, target)
        print(f"copied {relative.as_posix()} into {context.source_root}")
    sync_plan = plan_module.create_sync_plan(context, current, accepted=(relative,))
    return _apply_or_report(args, context, sync_plan, "add")
```

Give `add` the `--yes` flag and route it in `_dispatch`. In `parse_args`, replace the loop and the
`add` parser with:

```python
    for name in ("init", "plan", "sync", "publish", "validate"):
        child = sub.add_parser(name)
        _add_context_args(child)
        if name == "sync":
            child.add_argument("--yes", action="store_true")
    add = sub.add_parser("add")
    add.add_argument("path", type=Path)
    add.add_argument("--yes", action="store_true")
    _add_context_args(add)
```

and in `_dispatch`, add `"add": command_add,` to the `commands` mapping.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_add -v`, then the whole suite on both interpreters.
Expected: eight new tests PASS, suite OK at 221 tests.

- [ ] **Step 6: Commit**

```bash
git add artefact_sync/cli.py artefact_sync/plan.py tests/test_add.py
git commit -m "feat(add): stage one file into the source folder and sync that entry"
```

---

### Task 6: M3 acceptance — the add loop end to end, and SKILL.md

**Files:**
- Test: `tests/test_m3_end_to_end.py` (create)
- Modify: `SKILL.md`
- Modify: `docs/specs/plan_artefact-sync-m3.md` (status line, deviations)

**Interfaces:**
- Consumes: everything Tasks 1-5 produced. Adds no new interface.

- [ ] **Step 1: Write the acceptance test**

Create `tests/test_m3_end_to_end.py`:

```python
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from artefact_sync import cli
from tests.helpers import make_repo, make_source_tree

NOTE = b"# Cost model\n\nBuild versus buy, with the numbers.\n"


class AddLoopTests(unittest.TestCase):
    def test_add_then_delete_then_converge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {})
            inbox = root / "inbox"
            inbox.mkdir()
            (inbox / "Cost Model.md").write_bytes(NOTE)
            (inbox / "Client Curve.png").write_bytes(b"PNGDATA")
            pointer = root / "pointer.json"
            self.assertEqual(cli.EXIT_OK, cli.main(
                ["init", "--pointer", str(pointer), "--repo", str(repo), "--source", str(source)]))

            # add renders the Markdown page, links it, and needs no prior plan run.
            self.assertEqual(cli.EXIT_OK, cli.main(
                ["add", str(inbox / "Cost Model.md"), "--pointer", str(pointer), "--yes"]))
            published = repo / "artefacts"
            page = (published / "cost-model" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Build versus buy", page)
            self.assertIn("cost-model/", (published / "index.html").read_text(encoding="utf-8"))
            body = json.loads((published / "manifest.json").read_text())
            self.assertEqual(["general"], [c["id"] for c in body["collections"]])

            # A private-looking name warns, next to its URL, and still publishes.
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["add", str(inbox / "Client Curve.png"),
                                 "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_OK, code)
            self.assertIn('filename contains "client"', buffer.getvalue())
            self.assertTrue((published / "client-curve.png").is_file())

            # Deleting the source deletes the file, and says nothing about orphans.
            (source / "Client Curve.png").unlink()
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["sync", "--pointer", str(pointer), "--yes"])
            self.assertEqual(cli.EXIT_OK, code)
            self.assertNotIn("orphan", buffer.getvalue())
            self.assertFalse((published / "client-curve.png").exists())

            self.assertEqual(cli.EXIT_OK, cli.main(["validate", "--pointer", str(pointer)]))

            # Convergent: a second sync changes nothing.
            before = {path: path.read_bytes()
                      for path in sorted(published.rglob("*")) if path.is_file()}
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            after = {path: path.read_bytes()
                     for path in sorted(published.rglob("*")) if path.is_file()}
            self.assertEqual(before, after)

    def test_add_reports_excluded_files_it_did_not_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"notes.psd": b"binary", "drafts/wip.md": b"# w\n"})
            inbox = root / "inbox"
            inbox.mkdir()
            (inbox / "curve.png").write_bytes(b"PNGDATA")
            pointer = root / "pointer.json"
            cli.main(["init", "--pointer", str(pointer),
                      "--repo", str(repo), "--source", str(source)])
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["add", str(inbox / "curve.png"),
                                 "--pointer", str(pointer), "--yes"])
            text = buffer.getvalue()
            self.assertTrue((repo / "artefacts" / "curve.png").is_file())
        self.assertEqual(cli.EXIT_OK, code)
        self.assertIn("EXCLUDED", text)
        self.assertIn(".psd", text)
        self.assertIn("drafts/", text)
```

- [ ] **Step 2: Run it**

Run: `python3 -m unittest tests.test_m3_end_to_end -v` and again under `/usr/bin/python3`.
Expected: both PASS. Then the whole suite on both interpreters: OK at 223 tests.

- [ ] **Step 3: Update `SKILL.md`**

Replace the `add` bullet under "Commands":

```markdown
- `add <path>`: stage one file into the source folder and sync that entry. Copies the file in,
  refusing if a file of that name is already there; skips the copy when the path is already inside
  the source folder. The named file's proposed entry does not stop the run, since the file was named
  on purpose. Any other unlisted source still blocks it. Nothing becomes public until `publish`.
  `--yes` skips the confirmation for unattended runs.
```

and add a section after "Workflow":

```markdown
## Warnings

`plan`, `sync` and `add` print warnings next to the change groups. None of them stop a run.

- `secret`: a filename containing `prompt`, `draft`, `internal` or `client`, or a line matching an
  API-key, AWS-key, GitHub-token or private-key shape. Read the named line before publishing.
- `external`: a published HTML page loads something off-site at runtime. Vendor it into
  `artefacts/vendor/` and add a `replacements` entry if the page must keep working offline.
- `orphan`: a file in `artefacts/` belonging to no manifest entry. Never deleted, never rewritten.
- `size`: a new public file over 10 MB.

`EXCLUDED` lists what was in the source folder and did not sync: unsupported types by suffix, and
the `ignored_sources` rules that matched. A file that "did not publish" is almost always there.
```

- [ ] **Step 4: Run the full suite on both interpreters one last time**

Run:
```bash
python3 -m unittest discover -s tests -t . 2>&1 | tail -3
/usr/bin/python3 -m unittest discover -s tests -t . 2>&1 | tail -3
git -C /Users/keli/dev/github-kevinlin/kevinlin.github.io status --short
```
Expected: OK on both; the third command prints nothing.

- [ ] **Step 5: Record the result and commit**

Set this plan's status line, and fill in "Deviations from this plan" with every place the plan was
wrong — including corrected test counts. Then:

```bash
git add SKILL.md tests/test_m3_end_to_end.py docs/specs/plan_artefact-sync-m3.md
git commit -m "docs: record the M3 acceptance run and the add loop"
```

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

## Self-Review

**Spec coverage.** Walked the design's ladder line for M3 and every section it touches:

| Spec item | Task |
|---|---|
| `add <path>` copies into the source folder | 5 |
| `add` refuses on collision | 5 |
| `add` skips the copy when the path is already inside the source folder | 5 |
| `add` proposes one entry and syncs that entry | 5 (corrections M3-e, M3-f) |
| Secret-shape regexes surface as warnings | 3 |
| Filename heuristics (`prompts/`, `draft`, `internal`, `client`) surface as warnings | 3 (correction M3-c) |
| SVG validator gates `.svg`, rejecting and naming the line | Built in M1; Task 4 proves the `BLOCKED` row names the line |
| `plan` groups by consequence, full URLs, byte sizes | Built in M1; Task 4 adds the missing `EXCLUDED` group (correction M3-d) |
| Closed allowlist's three outcomes are distinguishable in output | 4 |
| Invariant 4: orphans are never deleted, and the message is true | 1 (correction M3-a) |
| Invariant 1: an existing entry is never re-titled or re-slugged | Unchanged. `add` passes only the new source in `accepted`; `propose` still runs solely on sources with no entry |
| Proposal quality on a first run | 2 (correction M3-b) |
| Testing ledger: "New surface: `add`, secret scan" | 3, 5 |

**Deliberately not done, and why.**

- **No live acceptance run.** M3 touches no networked code path: `add` writes local files, and the
  warnings are computed offline. M2's disposable-repo run already covered the provider seam, and M4's
  release gate is the next live run. A second probe repo here would cost half an hour to re-prove
  what row 6 of [m2-acceptance.md](m2-acceptance.md) proved.
- **`add` stages flat.** A file from outside the source folder lands at the source root, so it joins
  the `general` collection. No `--collection` flag, no destination override: the manifest is the
  place to move an entry, and it is one edit away. Add the flag when someone runs `add` and then
  edits the manifest every single time.
- **Dead ignore rules stay out of the plan.** `SyncPlan.ignored` drops zero-count rules, so a seeded
  rule that matches nothing is not four lines of noise on every run. `scan.apply_source_ignores`
  still returns every rule with its count, and `tests/test_scan.py` still pins that.
- **Warnings keep naming the source, not the URL.** The design's sample output block shows
  `secret    talk/cost-model.html:88`, a source path with a line number, because a line number in a
  rendered page helps nobody. "Next to the URL" means in the same output, and it already is.
- **The 40-hex secret rule keeps its false positives.** A page quoting a full git SHA warns. It is a
  warning, it costs one glance, and narrowing the rule to miss real secrets costs more.

**Type consistency.** `Note`, `Change`, `Blocked` and `SyncPlan` keep the field names M1 defined;
`SyncPlan` gains two defaulted fields, so `tests/test_plan.py` and `tests/test_apply.py`'s existing
positional constructions still work. `source_warnings(source, text)` has one signature across
Task 3's implementation, `tests/test_secrets.py`, and its one caller `_source_notes`.
`external_note(where, url)` is defined in `plan.py` in Task 3 and called from `plan._source_notes`
and `validate.validate_repository` under that name. `create_sync_plan`'s third parameter is
`accepted` in its definition, in `cli.command_add`, and in Task 5's tests. `_apply_or_report(args,
context, sync_plan, verb)` has the same argument order in its definition and both callers.
`ROOT_COLLECTION_LABEL` is read once, in `propose_manifest_additions`.

**Predicted counts.** 195 at the start, then 197, 199, 208, 213, 221, 223. Every one is a
prediction; see the last global constraint.

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

No correction to [design_artefact-sync.md](design_artefact-sync.md) was required by Tasks 1-4.

## Milestones after M3

- **M4** — the release gate. Copy `kevinlin.github.io`'s existing template verbatim into
  `page-template.html`, seed `date` from current mtimes, install the skill, run `plan` against the
  live tree, and require zero changes across its 57 entries. Rehome `build_showcase_atlas.py` first;
  it fires from `apply`/`publish` in the prior art and is not ported. M3's `EXCLUDED` block and
  widened filename heuristic will both fire loudly on that first run against 57 real entries: expect
  warnings, and expect them to be right.
