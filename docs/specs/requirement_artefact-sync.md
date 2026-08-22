# Requirement: artefact-sync

Status: agreed, not built
Date: 2026-08-22

## What it is

A user-space Claude Code skill that generalizes `kevinlin.github.io/scripts/artefacts.py` into a
portable tool. Public audience. One-way sync from a local source folder to an `artefacts/` tree in
an existing GitHub Pages repo.

Prior art: `scripts/artefacts.py` in `kevinlin.github.io`: 2310 lines, stdlib-only, unit-tested,
running against 57 manifest entries. The site-specific surface is small: `FAVICON_LINK`,
`MARKDOWN_PAGE_TEMPLATE`, `render_catalogue` and its `ARTEFACTS:START/END` markers, `HOMEPAGE_FILES`,
a hardcoded `origin/main`, the vendored `marked.min.js` path, and a `kevinlin.github.io` dirname
guard. Everything else is already generic: scan, manifest, diff, orphan detection, validate,
publish. The work is extraction from a working implementation.

Renamed from `my-artefacts`: `my-` reads as an unrenamed placeholder, and the bare word `artefacts`
collides with Maven, Azure DevOps, and GitHub Actions. British spelling stays: 57 published URLs
already use it.

## Topology

- Skill dir at `~/.claude/skills/artefact-sync/`: `SKILL.md` plus a stdlib-only Python 3 script.
  Nothing is installed into the destination repo. No CI.
- `artefacts/manifest.json` lives in the destination repo. Public URL mappings belong with the site,
  or a reinstall silently breaks every link ever published.
- A one-line user-space pointer `{repo, source}`, written by `init`. Commands work from any
  directory — you are never in the site repo when you make an artefact, you are in some project that
  just produced a diagram.
- Single target. Re-run `init` to change it.

Typical setup: `~/Downloads/Artefacts` -> `https://kevinlin.github.io/artefacts/`

## Commands

`init`, `plan`, `sync`, `add <file>`, `publish`, `validate`.

- `publish` keeps its existing meaning: make it live on the internet. That is the irreversible one,
  so staging a single file gets its own verb.
- `add <path>` copies the file into the source folder and syncs that one entry. `sync` stays a pure
  function of the source folder, which is the property everything else rests on.
- `publish` runs local validate and tests, pushes directly to `main`, waits for the Pages build, then
  fetches every published URL. Branch-and-PR sits behind a config flag for protected branches.

## Manifest

Existing schema, unchanged:

    {version, protected_files, ignored_sources, collections, entries}
    entry: {id, source, destination, title, collection, order, replacements}

Additions: optional `description` and `date`. `date` lets the catalogue sort by recency instead of
hand-maintained `order`. `replacements` survives, documented but unadvertised. It is the pressure
valve for an HTML file with an absolute path baked in.

`source` is relative to the source root, which lives in the user-space pointer rather than here, so
the manifest stays machine-independent. `destination` is frozen once published: a renamed source file
keeps its original destination, or the public URL breaks for anyone who shared it.

Worked example: [manifest.sample.json](manifest.sample.json).

## Rendering

Markdown keeps the client-side mechanism: source embedded verbatim in a
`<script type="text/markdown">` block, rendered by vendored `marked.js`. Byte-exact round-trip is
load-bearing for the diff preview and for `apply`'s verification. Rendering server-side reads as
cleaner and quietly deletes the invariant that proves what was published equals what was there.

Template and favicon become config values with neutral defaults, replacing the hardcoded colour
tokens and "K" favicon.

Catalogue: generate a standalone `artefacts/index.html` from the manifest by default. If config names
a host page containing the markers, inject there instead. Without one or the other, a synced folder
is a pile of unlinkable URLs.

## File types

Approved: `.html .md .png .jpeg .jpg .ico .pdf .webp .gif`.

`.svg` only behind a sanitiser stripping `<script>`, `on*` handlers, and external references, the same
spirit as the existing cdnjs ban. `.mp4` stays out; that is a Git-LFS conversation, and `.git` is
already 174MB.

Closed allowlist. A source file with no manifest entry stops the run and asks.

## Safety

- The model proposes manifest entries only for files it has never seen. An existing entry is never
  re-titled or re-slugged. That is how a live URL silently changes, so treat it as a hard
  constraint.
- `delete` (source gone) applies with one confirmation for the batch. `orphan` (in the repo, in no
  manifest) warns only. An unmanaged file might be a hand-written page, a redirect, or a `CNAME`, and
  deleting a `CNAME` on first run takes the user's domain down.
- `plan` groups by consequence, not by operation: new public URLs, changed content, URLs that will
  start 404-ing. Full URLs, spelled out. Byte sizes on adds, so a stray 40MB PNG is caught before
  `.git` swallows it.
- Secret-shape regexes and filename heuristics (`prompts/`, `draft`, `internal`, `client`) surface as
  warnings in `plan`, next to the URL. `init` seeds `ignored_sources` with `prompts/`, `drafts/`,
  `*.local.*`, and dotfiles so the first run is not a blank slate.
- Publishing is irreversible in practice. Search engines cache; deleting the file does not undo it.
  The skill says so out loud.
- Any failure stops and prints recovery for that state. No auto-rollback, no force-push — force-
  pushing someone's `main` on a transient network error is worse than the failure it cleans up.

## Portability

Push via plain `git`, so self-hosted hosts work without a code path. The provider layer covers only
the two things git cannot do: deriving the public URL from the remote, and waiting for the Pages
build. GitLab Pages URL patterns vary per instance, so config carries the base URL and provider
detection only guesses a default. `init` verifies that guess by fetching the URL once.

## Distribution

`git clone` into `~/.claude/skills/`, updates by `git pull`. The skill dir stays self-contained.

## Testing

Port `tests/test_artefacts.py`. It is the only artefact of what was already learned. Add a
disposable GitHub Pages repo for real end-to-end runs before release: auth, push, Pages build timing,
URL derivation, and deletion are exactly the steps unit tests mock out.

## Consequences accepted

- Strangers get no server-side gate. The last check before content goes public runs on the user's
  laptop and can be skipped. Post-push URL verification becomes the only proof a publish worked.
- `kevinlin.github.io` keeps its own copy and its `validate-artefacts.yml` workflow. The product
  ships with no consumer, and the two will drift.
- No marketplace means no version number. `manifest.version` has no source of truth, so a future
  schema change arrives with no migration signal.
- `apply` is non-atomic and can leave a half-written tree. Survivable only because the desired tree
  is a pure function of source plus manifest, so re-running converges.

## Out of scope

Site scaffolding, `.mp4` and Git-LFS, two-way sync, multiple targets, GitLab as a tested path.
