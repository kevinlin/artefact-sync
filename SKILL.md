---
name: artefact-sync
description: One-way sync a local folder into the artefacts tree of a configured GitHub Pages repository. Use when planning, applying, or validating published artefacts while preserving existing public URLs.
---

# artefact-sync

Sync approved files from one local source folder into `artefacts/` in one configured Pages repository. The manifest in the destination repository owns public paths and site settings. The machine-local pointer owns the source and repository paths.

Run commands from the skill root:

```bash
python3 -m artefact_sync <command>
```

From another directory, point Python at the installed skill:

```bash
PYTHONPATH="$HOME/.claude/skills/artefact-sync" python3 -m artefact_sync <command>
```

## Workflow

1. Run `init --repo <path> --source <path>` once. It writes the machine-local pointer and creates missing control files without replacing an existing manifest.
2. Run `plan`. Read every full URL, warning, deletion, and blocked item before continuing.
3. If `plan` exits 3 for unseen approved sources, inspect the proposed entries written to `artefacts/manifest.json`. This first run writes only the manifest. Run `sync` only after the destinations, titles, collections, and warnings are acceptable.
4. Run `sync`, type `yes` when prompted, then run `validate`.

The two-step proposal flow prevents a newly discovered file from becoming public before its URL and catalogue metadata are reviewed. Propose metadata only for sources absent from the manifest. Never re-title or re-slug an existing entry. A published entry keeps its `id`, `title`, and `destination`; a confirmed source rename takes the new `source` while retaining those fields.

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

## Commands

- `init`: configure the single repository and source folder, then seed missing control files.
- `plan`: show new public URLs, changed content, URLs that would start returning 404, warnings, and blocked files. An unseen approved source writes only its proposed manifest entry and exits 3.
- `sync`: recompute the plan, confirm it, apply atomic per-file writes, delete vanished managed entries, and leave unmanaged files alone. `--yes` is available for unattended verified runs.
- `validate`: check the manifest, required files, catalogue links, local references, and SVG policy. Unmanaged files are warnings.
- `add <path>`: stage one file into the source folder and sync that entry. Copies the file in,
  refusing if a file of that name is already there; skips the copy when the path is already inside
  the source folder. The named file's proposed entry does not stop the run, since the file was named
  on purpose. Any other unlisted source still blocks it. Nothing becomes public until `publish`.
  `--yes` skips the confirmation for unattended runs.
- `publish`: recompute the plan, confirm it, apply it, validate the tree, commit, push, wait for
  the Pages build, then fetch every published URL including protected files. Publishing is
  irreversible in practice: search engines and readers may cache a URL once it is public, and
  deleting the file later does not undo that. State this before running it.

Commands accept `--repo` and `--source` overrides. Tests may also pass `--pointer`; normal use relies on `~/.config/artefact-sync/config.json`.

## Publishing

`publish` needs `git`, and needs `gh` authenticated when the remote is GitHub. It refuses to start
unless the working tree is clean outside `artefacts/`, the checkout is on the default branch, and
that branch matches `origin`. Set `"push": "branch"` in `~/.config/artefact-sync/config.json` for a
protected default branch: `publish` then pushes a timestamped branch, prints the pull request URL,
and stops without making anything live.

Every failure stops and prints the recovery for that exact state. Nothing force-pushes and nothing
rolls back automatically. If a publish fails after the push, re-run `publish`: with no changes left
it re-verifies the published URLs and reports.

## Manifest

`artefacts/manifest.json` has this shape:

```text
{
  version,
  site: {base_url, favicon, catalogue: {mode, page?}},
  protected_files,
  ignored_sources,
  collections: [{id, title, description?, section, section_order, order}],
  entries: [{id, source, destination, title, collection, order,
             replacements, description?, date?}]
}
```

`source` is relative to the configured source folder. `destination` is relative to `artefacts/` and is frozen after publication. HTML replacements are ordered raw-text substitutions. Missing `date` values are stamped from source modification time on the first sync and then stored in the manifest.

Approved types are `.html`, `.md`, `.png`, `.jpeg`, `.jpg`, `.ico`, `.pdf`, `.webp`, `.gif`, and `.svg`. SVG files are validated and copied byte-for-byte, never sanitised or rewritten. Unsupported types are excluded. Approved but unlisted files block.

## Safety

- Treat `plan` as the decision surface. Do not apply blocked plans.
- Do not delete or rewrite unmanaged files. Orphans are warnings only.
- Do not change an existing title or destination to resolve a proposal conflict.
- Do not force-push or attempt automatic rollback.
- State the practical irreversibility before any future `publish` operation.

## Vendored dependency

The bundled `artefact_sync/assets/marked.min.js` is marked 15.0.12, copyright 2011-2025 Christopher Jeffrey, licensed under the MIT License.
