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

## Commands

- `init`: configure the single repository and source folder, then seed missing control files.
- `plan`: show new public URLs, changed content, URLs that would start returning 404, warnings, and blocked files. An unseen approved source writes only its proposed manifest entry and exits 3.
- `sync`: recompute the plan, confirm it, apply atomic per-file writes, delete vanished managed entries, and leave unmanaged files alone. `--yes` is available for unattended verified runs.
- `validate`: check the manifest, required files, catalogue links, local references, and SVG policy. Unmanaged files are warnings.
- `add <path>`: reserved for M3. It is not available in M1.
- `publish`: reserved for M2. It is not available in M1. Publishing is irreversible in practice because search engines and downstream readers may cache a URL after it becomes public.

Commands accept `--repo` and `--source` overrides. Tests may also pass `--pointer`; normal use relies on `~/.config/artefact-sync/config.json`.

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
