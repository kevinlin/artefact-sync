# artefact-sync M1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status: complete.** All 16 tasks implemented; 131 tests pass on both `/usr/bin/python3` (3.9.6,
the floor) and 3.13. Tasks 3-4, 5-6 and 7-8 share a file each and landed as one commit per pair; the
rest got one commit apiece. Six review findings were fixed in a follow-up round, listed in
"Deviations from this plan" below.

**Goal:** Build the portable core of `artefact-sync` (`init`, `plan`, `sync`, `validate`), working
against a local repo with no network access.

**Architecture:** A stdlib-only Python package inside the skill directory. `cli.py` resolves
`(repo_root, source_root, site)` once into a frozen `Context` before dispatch; every core function
takes it as an argument so nothing below the CLI reads `~`, `cwd` or `__file__`. Dependency
direction is one-way (`cli` → `plan` → `render`/`catalogue`/`scan` → `manifest` → `errors`), which
keeps the core testable with no git, no network and no repo on disk.

**Tech Stack:** Python 3.9, standard library only, `unittest`.

**Spec:** [design_artefact-sync.md](design_artefact-sync.md). Its supporting evidence, with
`file:line` citations into the prior art, is [extraction-analysis.md](../research/extraction-analysis.md).

## Global Constraints

Every task's requirements implicitly include this section.

- **Python 3.9.** The tool must run under stock macOS `/usr/bin/python3` (3.9.6). Every module
  starts with `from __future__ import annotations` so `X | None` annotations parse on 3.9.
- **Standard library only.** No third-party import in the shipped package or in its tests, ever.
- **Test command:** `python3 -m unittest discover -s tests -t . -v`. Never pytest.
- **British spelling** in every user-facing string, path and identifier: `artefacts`, `catalogue`.
  57 published URLs already use it.
- **No emoji** in any output.
- **Repo root is the skill directory.** This repo is cloned to `~/.claude/skills/artefact-sync/`.
  `SKILL.md` sits at the root next to the `artefact_sync/` package.
- **Prior art, read-only:** `/Users/keli/dev/github-kevinlin/kevinlin.github.io/scripts/artefacts.py`
  and `tests/test_artefacts.py`. When a task says "port from `artefacts.py:X-Y`", open those exact
  lines and carry the behaviour across. Do not invent behaviour a citation does not support.
- **Never write to `/Users/keli/dev/github-kevinlin/kevinlin.github.io`.** It is a live site with 57
  published URLs. Read it; do not touch it. `git -C <that repo> status --short` must stay empty.
- **Exit codes:** `0` success, `1` error, `3` blocked and needs a human decision.

---

## File Structure

```
artefact-sync/                    repo root == skill directory
  SKILL.md                        how the model drives the tool
  artefact_sync/
    __init__.py
    errors.py                     exception types shared across modules
    config.py                     pointer file + site block -> Context
    manifest.py                   models, decode, validate, normalise, HEAD invariants
    scan.py                       source walk, ignore rules, allowlist, SVG validation
    render.py                     markdown page rendering, HTML transformation
    catalogue.py                  standalone shell generation, marker injection
    propose.py                    slug/title/collection derivation, rename detection
    plan.py                       diffing, consequence grouping, plan formatting
    apply.py                      atomic writes, deletions, verification
    cli.py                        parser, Context resolution, dispatch, exit codes
    assets/
      page-template.html          neutral $-placeholder artefact page
      catalogue-template.html     neutral standalone catalogue shell
      marked.min.js               vendored renderer, copied into repos by init
  tests/
    __init__.py
    helpers.py                    fixture source tree and destination repo builders
    test_stdlib_only.py           guard: no third-party imports
    test_config.py  test_manifest.py  test_scan.py  test_render.py
    test_catalogue.py  test_propose.py  test_plan.py  test_apply.py
    test_cli.py  test_init.py  test_m1_end_to_end.py
```

`errors.py` exists so `manifest.py` and `scan.py` can raise the same exception types without
importing each other. `models` are not a separate file: `Collection`/`Entry`/`Manifest` live in
`manifest.py`, `Site`/`Context` in `config.py`, `Change`/`Note`/`SyncPlan` in `plan.py` — each beside
the code that owns it, with no cycles.

`publish.py`, `provider.py` and `selfcheck.py` are M2. They are named here only so nobody adds them
early.

---

## Implementation Tasks

### Task 1: Skeleton, test harness, and the stdlib-only guard

Created the package skeleton (`artefact_sync/__init__.py`, `errors.py`) and a `test_stdlib_only.py` guard that AST-walks every module to reject third-party imports and enforce `from __future__ import annotations`. Established the shared test helpers (`make_source_tree`, `make_repo`).

**Produces:** `ArtefactSyncError`, `ConfigError`, `ValidationError`, `TransformationError`, `UnlistedSources` with attribute `sources: tuple[PurePosixPath, ...]`.

---

### Task 2: `config.py` — pointer file, site block, Context

Built the pointer-file mechanism (`~/.config/artefact-sync/config.json`) and the `Context` dataclass that freezes all path resolution before dispatch. Wholly new code — the prior art derived defaults from the script's own parent directory.

**Produces:** `POINTER_PATH`, `Pointer(repo, source, push)`, `Site(base_url, favicon, catalogue_mode, catalogue_page)`, `Context(repo_root, source_root, artefacts_root, site)`, `load_pointer`, `save_pointer`, `site_from_dict`, `site_to_dict`, `build_context`.

---

### Task 3: `manifest.py` — models, decode, validate, serialise

Ported schema parsing and validation from `artefacts.py:215-446` and `artefacts.py:1394-1433`. Three deltas from the prior art: `APPROVED_EXTENSIONS` gained `.pdf .webp .gif .svg`; `Entry` gained `description` and `date`; `Manifest` gained `site`.

**Produces:** `Collection`, `Entry`, `Manifest`, `manifest_from_dict`, `manifest_to_json`, `manifest_from_bytes`, `validate_manifest`, `normalize_orders`, `load_manifest`, `APPROVED_EXTENSIONS`, `DIRECTORY_INDEX_EXTENSIONS`, `MANIFEST_NAME`, `TEMPLATE_NAME`, `CATALOGUE_NAME`.

---

### Task 4: `manifest.py` — the published-URL invariants

Added `head_manifest` (reads `git show HEAD:artefacts/manifest.json`) and `check_published_invariants` which rejects destination or title changes on existing entries. This is new enforcement not ported from the prior art — nothing today compares against HEAD.

**Produces:** `head_manifest(repo_root) -> Manifest | None`, `check_published_invariants(current, head) -> None`.

---

### Task 5: `scan.py` — walk, allowlist, glob ignores

Ported from `artefacts.py:447-524`. Replaced the hardcoded `kevinlin.github.io` directory prune with pruning the resolved destination repo when it sits under the source root. Added `fnmatch` to `is_ignored` so `*.local.*` and `.*` rules work.

**Produces:** `SourceInventory(approved, excluded)`, `scan_source`, `is_ignored`, `apply_source_ignores`.

---

### Task 6: `scan.py` — the SVG validator

Added a line-oriented validator that refuses SVGs containing scripts, event handlers, external references, `foreignObject`, or entity declarations. Per spec D3 this is a validator, never a rewriter — files ship byte-identical.

**Produces:** `validate_svg(data: bytes, label: str) -> None`.

---

### Task 7: `render.py` — Markdown pages on `string.Template`

Ported escape/unescape/extract from `artefacts.py:525-895`. The 219-line branded template became `assets/page-template.html`, de-branded and switched from `str.format` to `string.Template` (eliminates 55 doubled-brace escapes).

**Produces:** `escape_markdown_block`, `unescape_markdown_block`, `extract_markdown`, `markdown_vendor_path`, `load_template`, `render_markdown_page`, `markdown_diff`.

---

### Task 8: `render.py` — HTML transformation and external-reference warnings

Ported `ensure_favicon` and `transform_html` from `artefacts.py:1208-1277`. Replaced the cdnjs-specific rejection with `external_references` which reports every off-site reference for `plan` to warn about and blocks none.

**Produces:** `transform_html`, `external_references`, `build_desired_files`.

---

### Task 9: `catalogue.py` — standalone generation and marker injection

Ported injection from `artefacts.py:1280-1391`. Added standalone catalogue generation (didn't exist in the prior art — a repo holding only a manifest couldn't run before). Deleted `collect_source_timestamps`; dates now come from the manifest per spec E1.

**Produces:** `CATALOGUE_START`, `CATALOGUE_END`, `render_catalogue`, `render_standalone_catalogue`, `replace_generated_catalogue`, `entry_sort_key`.

---

### Task 10: `propose.py` — entry proposals and rename detection

Ported slug derivation from `artefacts.py:897-1205`. Replaced the personal-site taxonomy with one neutral default. Added content-hash rename detection so a renamed source keeps its published destination instead of silently changing a live URL.

**Produces:** `suggest_destination`, `detect_renames`, `propose_manifest_additions`, `DEFAULT_SECTION`.

---

### Task 11: `plan.py` — planner and consequence grouping

Ported from `artefacts.py:1436-1654`. `Change` gained `source`, `size`, `url` and `diff`. Orphans became warnings (`Note`) instead of deletions. `format_plan` groups by consequence (new URLs / changed / will 404 / warnings / blocked) rather than by operation.

**Produces:** `Change`, `Note`, `Blocked`, `SyncPlan`, `create_sync_plan`, `format_plan`, `DELETION_KINDS`.

---

### Task 12: `apply.py` — atomic writes and round-trip verification

Ported from `artefacts.py:1657-1721`. Orphans are never unlinked. The round-trip check now actually extracts the embedded Markdown back out and compares it, replacing the prior art's tautological check.

**Produces:** `apply_plan`, `verify_markdown_round_trip`, `_write_atomic`, `_resolve_within`.

---

### Task 13: `cli.py` — Context resolution, dispatch, exit codes

Ported from `artefacts.py:2250-2336`. Deleted `default_repo_root`/`default_source_root` (derived the repo from the script's own parent). Defaults now come from the pointer file; `--repo` and `--source` survive as overrides.

**Produces:** `main(argv) -> int`, `EXIT_OK = 0`, `EXIT_ERROR = 1`, `EXIT_BLOCKED = 3`, `resolve_context`, `parse_args`.

---

### Task 14: `init` — create the pointer and seed the destination repo

Wholly new. Writes `vendor/marked.min.js` and `page-template.html`, registers the vendor in `protected_files`, seeds `ignored_sources` with working glob rules, and guesses the GitHub Pages base URL from the remote.

**Produces:** `command_init`, `derive_base_url`.

---

### Task 15: `validate` and `sync` commands

Ported `validate_repository` from `artefacts.py:1757-1823` minus the `HOMEPAGE_FILES` diff guard and cdnjs rejection. Unmanaged files became warnings (spec E2). Added `--yes` flag to `sync` for unattended testing.

**Produces:** `command_validate`, `command_plan`, `command_sync`, `validate_repository`.

---

### Task 16: M1 acceptance — end to end against a fixture repo

Proved the full loop: `init` → `plan` (blocks on unlisted) → `sync --yes` → `validate` → second sync (convergent). Wrote `SKILL.md`.

---

## Critical Files — Summary

| Path | Role |
|---|---|
| `artefact_sync/errors.py` | Shared exception types |
| `artefact_sync/config.py` | Pointer file, Site, Context |
| `artefact_sync/manifest.py` | Schema, decode, validate, HEAD invariants |
| `artefact_sync/scan.py` | Source walk, SVG validator |
| `artefact_sync/render.py` | Markdown pages, HTML transform, external refs |
| `artefact_sync/catalogue.py` | Standalone/inject catalogue generation |
| `artefact_sync/propose.py` | Slug derivation, rename detection |
| `artefact_sync/plan.py` | Diffing, consequence grouping, formatting |
| `artefact_sync/apply.py` | Atomic writes, round-trip verification |
| `artefact_sync/cli.py` | Argparse, context resolution, dispatch |
| `artefact_sync/assets/page-template.html` | Neutral `$`-placeholder page |
| `artefact_sync/assets/catalogue-template.html` | Standalone catalogue shell |
| `artefact_sync/assets/marked.min.js` | Vendored client-side renderer |
| `SKILL.md` | How the model drives the tool |

---

## Self-Review

**Spec coverage.** Walked each section of [design_artefact-sync.md](design_artefact-sync.md):

| Spec item | Task |
|---|---|
| D2 config split, D2a template file | 2, 7 |
| D3 SVG validator | 6 |
| E1 date stamped and frozen | 3, 9 |
| E2 orphans warn, validate stops erroring | 11, 12, 15 |
| E3 fnmatch globbing | 5, 14 |
| E4 external references warn | 8 |
| E5 round-trip restated and actually verified | 7, 12 |
| E6 no `CNAME` in the sample | n/a — sample lives in the spec folder, corrected there |
| Invariant 1 and 2 (no re-title, frozen destination) | 4 |
| Invariant 3 (rename keeps destination) | 10 |
| Invariant 4 (orphans never deleted) | 11, 12 |
| Invariant 5 (no auto-rollback, no force-push) | M2 — nothing in M1 pushes |
| Topology, cwd independence | 2, 13 |
| Commands `init` `plan` `sync` `validate` | 14, 15 |
| Command `add` | M3 |
| Command `publish`, provider, self-check | M2 |
| Testing ledger | tasks 3-15 carry the ported areas; publish's 20 cases are M2 |

**Gaps, stated rather than hidden.** `add` is M3 and `publish`/`provider`/`selfcheck` are M2, per the
spec's own ladder. `init` guesses the base URL but does not fetch it to verify — that needs network
and belongs with the provider in M2. Task 15's `--yes` flag is a testing affordance the spec does not
mention; it exists so the convergence test can run unattended, and `sync` still confirms
interactively by default.

**Type consistency.** `Context`, `Site`, `Pointer`, `Entry`, `Manifest`, `Change`, `Note`, `Blocked`
and `SyncPlan` are each defined once, in the task that introduces them, and every later task's
Interfaces block names the same fields. `DELETION_KINDS` is defined in `plan.py` (Task 11) and
consumed in `apply.py` (Task 12) under that name. `markdown_vendor_path` is defined in Task 7 and
used in Task 14 with the same signature.

---

## Deviations from this plan

Recorded because the plan was written before the code existed, and a plan that hides where it was
wrong is worth less on the next milestone.

Plan defects found and corrected during implementation:

- Task 10's `ProposalTests` body was `pass`, asserting nothing. Replaced with the rename assertion
  the surrounding prose describes.
- Task 12's first test was a conditional expression. It asserted nothing on its failing branch, so it
  was rewritten to render through `render_markdown_page` and check the round trip for real.
- Task 12 named both `apply_plan` and `apply_plan_files`. Standardised on the former.
- Task 7's template, lifted from the prior art, kept `getElementById('markdown-source')` while the
  new `BLOCK_START` renamed the id to `artefact-source`, and kept `src="$prefix$vendor"` while the
  new caller already prefixes the path. Either would have shipped a broken page with every unit test
  green — the vendor one because `../../vendor/...` is a substring of `../../../../vendor/...`. Both
  fixed, both now pinned by exact assertions.
- Task 7's template also kept `.replace(/^\n/, '')` in its JS, correct in the prior art where the
  newline lived inside the block-start constant, wrong once it did not. It silently ate a leading
  blank line in the browser while Python's round trip stayed green. Removed, and pinned by a test
  that asserts on the template text, since no Python-only test can see it.
- Task 13's fixtures needed a manifest before `resolve_context` could read the site block.
- Task 3's `Collection.description` had to become optional. The plan's own fixtures already assumed
  that; its port note never said so.

Review findings fixed after Task 16:

- The path-containment guard had been duplicated across `manifest.py` and `apply.py`, regressing a
  one-implementation decision the prior art documents explicitly. Collapsed to
  `manifest.resolve_within`, with `apply`'s extra symlinked-parent walk layered on top rather than
  reimplemented beneath.
- Private names were being imported across module boundaries. `manifest.is_ignored`,
  `manifest.resolve_within` and `apply.write_atomic` are now public where they are owned.
- Declining the `sync` confirmation exited 1 with no output. It still exits non-zero, so
  `sync && publish` cannot proceed after a refusal, but it now says nothing was applied.
- Two `assert` statements guarded a runtime path invariant and would vanish under `python -O`.
  Replaced with `ValidationError`.
- `validate_svg` sorted its findings as strings, so `:10` preceded `:2`. Now sorted numerically.

Design corrections this implementation forced, applied to
[design_artefact-sync.md](design_artefact-sync.md):

- Rename-by-hash is exact only for byte-copy formats. Markdown must compare extracted embedded
  source, and transformed HTML has no published bytes equal to its source at all.
- The "nothing below the CLI reads `__file__`" rule is about repository and source resolution.
  Bundled-asset fallback legitimately resolves relative to the installed package.
- `plan.py` depends on `propose.py`, which the module graph omitted.
- `plan` is not a pure read: its blocked path writes the proposed manifest.
- `Collection.description` is optional, and absent optional fields are omitted rather than nulled.
- `page-template.html` is a reserved destination alongside `manifest.json` and `index.html`.

Scope left as the design's ladder intended: `add` is M3; `publish`, `provider.py` and `selfcheck.py`
are M2. `init` guesses the Pages URL from the remote but does not fetch it to verify — that needs
network and lands with the provider in M2.

## Milestones after M1

M2, M3 and M4 get their own plans, written once M1 lands. Their shape depends on what M1's provider
seam actually turns out to need, and writing them now would mean guessing at it.

- **M2** — `publish`, `provider.py`, `selfcheck.py`, and a disposable GitHub Pages repo. Rewrites all
  20 publish tests: every one currently assumes `gh`, a PR, and a check named `validate`.
- **M3** — `add <path>`, and whatever `plan`'s warnings need after real use.
- **M4** — the release gate. Copy `kevinlin.github.io`'s existing template verbatim into
  `page-template.html`, seed `date` from current mtimes, install the skill, run `plan` against the
  live tree, and require zero changes across its 57 entries. Rehome `build_showcase_atlas.py` first;
  it is triggered from `apply`/`publish` today and is not ported.

---

## Changelog

- 2026-08-23 — **Compacted post-implementation.** Removed step-by-step tasks, file-by-file diffs, code snippets, and verification commands now that the feature has shipped. Preserved Goal, Architecture, Global Constraints, File Structure, per-task interface summaries, Self-Review, Deviations, and Milestones. Original plan recoverable via git history.
