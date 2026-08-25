# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

The `artefact-sync` Claude Code skill, installed by `git clone` into `~/.claude/skills/artefact-sync/`.
It one-way syncs a local source folder into the `artefacts/` tree of a GitHub Pages repo, preserving
published URLs. [SKILL.md](SKILL.md) is the user-facing contract. Behaviour changes must land there
too, or the skill documents something it no longer does.

## Commands

```bash
# whole suite (245 tests, ~11s). Run on BOTH interpreters before calling anything done.
python3 -m unittest discover -s tests -t .
/usr/bin/python3 -m unittest discover -s tests -t .   # macOS stock 3.9.6 — the version floor

python3 -m unittest tests.test_plan -v                # one module
python3 -m unittest tests.test_plan.PlanTests.test_x  # one test
python3 -m unittest discover -s tests -t . -k svg     # by name

# run the tool itself (works from any directory, no PYTHONPATH)
python3 scripts/artefact_sync.py plan
```

No pytest, no deps, no venv, no CI. `tests/__init__.py` puts `scripts/` on `sys.path`; run from the
repo root so that import works.

## Hard constraints (each has a test that fails if you break it)

- **Stdlib only, Python 3.9.6 floor.** `tests/test_stdlib_only.py` walks every module's AST against an
  explicit allowlist and requires `from __future__ import annotations` at the top of each file (that's
  what makes `X | None` parse on 3.9). External binaries are `git` and `gh`, never libraries.
- **Flat module namespace.** `scripts/*.py` import each other by bare name (`from errors import ...`)
  because running a file in `scripts/` puts that directory on `sys.path`. No package, no relative
  imports.
- **Nothing below the CLI resolves paths.** `cli.py` resolves `(repo_root, source_root, site)` exactly
  once into a frozen `config.Context` and passes it down. No core function reads `~`, `cwd` or
  `__file__`. The single exemption is `config.ASSETS`, the skill's own bundled templates.
- **git and network behind an injectable seam.** `provider.CommandRunner` and `provider.Fetcher` are
  callables; `tests/helpers.RecordingRunner` answers from a longest-prefix table, so the whole suite
  runs with no git repo and no network.

## Architecture

Dependency direction is one-way, so the core is testable with no git, no network, no repo on disk:

```
cli.py ──► config.py ──► pointer file, manifest site block
  ├──► scan.py ──► manifest.py
  ├──► propose.py ──► manifest.py
  ├──► plan.py ──► render.py, catalogue.py, scan.py, propose.py
  ├──► apply.py ──► plan.py
  └──► publish.py ──► apply.py, provider.py, git
```

`plan.py` is the decision surface: `create_sync_plan` produces the change groups the CLI prints and
`apply.py` executes. Exit codes: `0` ok, `1` error, `3` blocked (an approved source with no manifest
entry). A blocked `plan` writes the proposed `manifest.json` and nothing else — that two-step flow is
what stops a newly discovered file going public before its URL is reviewed.

Three state locations, one owner each:

| Where | Holds |
|---|---|
| this repo (`~/.claude/skills/artefact-sync/`) | code, `assets/page-template.html`, vendored `marked.min.js` |
| `~/.config/artefact-sync/config.json` | `repo`, `source`, `push` (machine-local pointer) |
| `<repo>/artefacts/` | `manifest.json`, `page-template.html`, `index.html`, `vendor/`, published tree |

## Invariants that protect published URLs

These are the reason the code is shaped the way it is. Changing them changes what breaks for readers.

- An existing entry is never re-titled or re-slugged; `destination` is frozen once published.
  Enforced by `manifest.check_published_invariants` against `git show HEAD:artefacts/manifest.json`.
  `propose.py` runs only on sources with no entry.
- Orphans (files in `artefacts/` belonging to no entry) are warned about, never deleted or rewritten.
- No force-push, no automatic rollback. Every failure stops and prints recovery for that exact state.
- Markdown round-trips text-exact after `render.normalise_source_text` (UTF-8 decode, CRLF/CR → LF,
  trailing newline). Anything less and `core.autocrlf` makes an unchanged entry report CHANGED forever.
- The embedded block is `<script type="text/markdown" id="markdown-source">` plus a newline, and
  templates compose `src="$prefix$vendor"` (`$prefix` is the `../` climb, `$vendor` the path alone).
  Both spellings match what the prior art published; changing either rewrites every page an adopter has.
- SVG is validated and copied byte-for-byte: reject and name the line, never sanitise.

## Docs

- [docs/specs/design_artefact-sync.md](docs/specs/design_artefact-sync.md) is authoritative on
  behaviour and carries the numbered deviations (D1-D7, E1-E6, M4-a…k) with the reason for each. Read
  it before arguing with a design choice; the reason is usually already there.
- The M1-M4 plans under [docs/specs/](docs/specs/) are historical records. They describe the layout as
  it was at the time. Leave them alone.
- [CHANGELOG.md](CHANGELOG.md) groups milestones under a release; releases are git tags, and
  `SKILL.md`'s `metadata.version` names the current one. Add to `## Unreleased` above the newest
  release, creating that heading if it isn't there.
