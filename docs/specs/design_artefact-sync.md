# Design: artefact-sync

Status: M1 to M4 built. `init`, `plan`, `sync`, `add`, `validate` and `publish` ship. The provider
seam has live evidence: the M2 acceptance run passed fifteen rows against a disposable Pages
repository ([m2-acceptance.md](m2-acceptance.md)). The extraction has fidelity evidence: M4's gate
reproduced a prior-art-published tree byte for byte ([m4-acceptance.md](m4-acceptance.md)).
Migrating `kevinlin.github.io` is a follow-on, not a milestone gate - see M4-h.
Date: 2026-08-25

Refines [requirement_artefact-sync.md](requirement_artefact-sync.md) against what the prior art
actually does. Every behavioural claim here is sourced from
[extraction-analysis.md](../research/extraction-analysis.md), which cites `file:line` in
`kevinlin.github.io` for each one. Where this document and the requirement disagree, this one wins,
and the disagreement is listed in "Changes to the requirement" below.

## Changes to the requirement

The requirement was written from memory of the script. The analysis read it. Fourteen things moved.

| # | Requirement said | Design says | Why |
|---|---|---|---|
| D1 | The two copies drift; the product ships with no consumer | `kevinlin.github.io` migrates onto the skill, and that migration is the release gate | An untested product with one real installation running different code is not a shipped product |
| D2 | Config values unplaced | Site settings in a `site` block in `manifest.json`; machine paths in `~/.config/artefact-sync/config.json` | The reason the manifest lives with the site applies identically to what renders it |
| D2a | (not addressed) | The page template is a real file, `artefacts/page-template.html`, not a JSON string | A 219-line HTML string inside JSON is unreadable and undiffable |
| D3 | `.svg` behind a sanitiser | `.svg` behind a validator: reject and name the line, never rewrite | A stdlib sanitiser that misses `foreignObject`, `xlink:href` or CSS `url()` is worse than none, because the user then trusts it. Rewriting also breaks the round-trip invariant |
| D4 | `publish` runs "validate and tests" | `validate` plus a sub-second install self-check | A stranger publishing a diagram should not run 2,500 lines of unit tests. The self-check exists only for the corrupted-`git pull` case, which CI cannot see |
| D5 | Nothing is installed into the destination repo | `init` writes `vendor/marked.min.js` and `page-template.html` into it | Publishing Markdown is impossible without a `protected_files` entry named `marked.min.js`. They are site content rather than tool code, so the rule still holds for code and CI |
| D6 | Branch-and-PR behind a config flag | Protected-branch mode pushes the branch, prints the URL, stops | Automating PRs needs `gh` and grows the provider from 2 operations to about 6, which falsifies the requirement's own portability claim |
| D7 | `sync` and `publish` separate | `publish` always recomputes and applies, then pushes | The desired tree is a pure function of source + manifest, so recompute is a no-op when `sync` already ran. Removes an entire out-of-sync error class, and resolves the preflight conflict where a prior `sync` would leave a tree the old preflight rejects |
| E1 | `date` lets the catalogue sort by recency | `date` absent means the first `sync` stamps it from source mtime and freezes it into the manifest | The catalogue reads mtime live today, so re-downloading an unchanged file changes its card date and reorders the page |
| E2 | Orphans warn only | Orphans warn only, and `validate` stops erroring on them | Today `validate` rejects every unmanaged file, so a warned-but-kept orphan would fail `publish`'s own gate |
| E3 | `init` seeds `*.local.*` and dotfiles | Same seeds, plus an `fnmatch` engine so they match | Matching is exact-string or literal `dir/` prefix, so `*.local.*` would match nothing and publish the files it was meant to hide |
| E4 | The `.svg` gate is "the same spirit as the existing cdnjs ban" | The cdnjs ban generalises: warn on any external reference in HTML, block none | The current rule blocks one CDN by raw substring and permits every other remote host |
| E5 | Markdown round-trip is byte-exact | Text-exact after UTF-8 decode and trailing-newline normalisation | Rendering rejects non-UTF-8 and appends a missing final newline. `apply` also never verified the round trip; it compared rendered bytes to the rendered bytes it had just computed |
| E6 | `protected_files` can hold `CNAME` to protect the domain | Dropped from the sample | `protected_files` resolve under `artefacts/`, so it meant `artefacts/CNAME`. The repo-root `CNAME` was never reachable by orphan scanning |
| M4-a | Template placeholders are `$title, $favicon, $prefix, $vendor, ...` | `$vendor` is the vendor path alone; `$prefix` is the `../` climb; the shipped template composes `src="$prefix$vendor"` | `render_markdown_page` passed `vendor=prefix + vendor_path`, and the shipped template used `$vendor` on its own, so the two placeholders could not both be used as documented. A template using both, as the prior art's does, produced `../../../../vendor/marked.min.js` |
| M4-b | E5: the invariant is "text-exact after UTF-8 decode and trailing-newline normalisation" | Text-exact after UTF-8 decode, **line-ending normalisation**, and trailing-newline normalisation | Git with `core.autocrlf=input` - a common default - stores LF for a CRLF working-tree file. Without normalisation the bytes `apply` writes are not the bytes that get published, and a fresh clone reports the same entry CHANGED on every run, forever. Normalising CRLF to LF is safe for Markdown: a hard line break is trailing spaces or a backslash, never a CR |
| M4-c | The Markdown block is `<script type="text/markdown" id="artefact-source">` | `<script type="text/markdown" id="markdown-source">` followed by a newline | That is what the prior art published (`artefacts.py:525-526`). Keeping the skill's spelling rewrites every Markdown page an adopter has, and `extract_markdown` cannot read any of them, so the diff preview and `apply`'s round-trip check both go blind on exactly the pages an adoption needs to check |
| M4-d | "`date` lets the catalogue sort by recency instead of hand-maintained `order`" | Collection **cards** sort by their newest entry date, descending, stable on `order`. **Entries** inside a card keep sorting by `order` | The prior art sorts cards by recency and entries by `order` (`artefacts.py:1360-1383`). Sorting entries by date too reorders any curated collection, and it is the wrong reading anyway: a card's date answers "is this collection fresh", while an entry's position inside a card is editorial |
| M4-e | "Customising the standalone catalogue means adding markers to it and switching to inject mode, so there is no second template" | True for the shell, false for the fragment. `render_catalogue` adopts the prior art's markup | The fragment's class names are what the host page's CSS targets, so a host page cannot adopt a foreign fragment without a rewrite. Making the tool's markup the prior art's is what lets any existing inject-mode page keep its stylesheet |
| M4-f | `head_manifest` returns "the manifest as of HEAD, or None when it was never committed" | Also `None` when HEAD's manifest cannot be parsed, after one attempt with a placeholder `site` injected | A repository adopting the skill has a committed manifest with no `site` block, and the invariant check reads only `id`, `destination` and `title` from it. Failing the whole run on a field the check never touches makes adoption impossible; returning `None` immediately would throw away the URL-freeze guard on precisely the run where published destinations are at stake. Injecting a placeholder keeps the guard |
| M4-g | `HOMEPAGE_FILES` is part of the site-coupling surface still to port | Not ported | It backs a `git diff --exit-code base...HEAD -- index.html styles.css script.js` check. `publish`'s preflight already refuses any change outside `artefacts/`, which is strictly stronger and needs no base ref |
| M4-h | M4 is "the release gate, migrating `kevinlin.github.io`", and the migration "has to rehome the atlas" | The gate runs against a disposable probe pair. `kevinlin.github.io` is untouched, so its `scripts/artefacts.py`, its `validate-artefacts.yml` and its atlas hook all stay exactly as they are | Deferred by the milestone's owner. The extraction proof does not need the live site's URLs at risk, and the fixes M4 lands are most of what makes the live migration a no-op whenever it is taken. D1 still stands as the eventual destination; it is no longer M4's gate |
| M4-i | `ignored_sources` matching "is currently exact-string or literal `dir/` prefix", widened by E3 to `fnmatch` | Recorded as a migration hazard, with a test. A bare `name/` rule matches that directory **at any depth** in the skill; in the prior art it matches only at the root | Found by the probe corpus: `prompts/` ignores `mingpt-vs-toy-transformer/prompts/infographic.md` under the skill and nothing under the prior art. The skill's behaviour is deliberate (`manifest.is_ignored` checks `directory in source.parts[:-1]`) and better, but a manifest carried over from the prior art can start ignoring files it used to publish, and those show up as deletions. The live manifest happens to be safe because all three of its `prompts/` rules carry full prefixes |
| M4-j | (not addressed) | `site.catalogue.section_links` is **not** built | The prior art injects a 3D showcase link into the `Image collections` heading unconditionally, and regenerating that heading would delete it. The probe corpus produces one section and no such link, so nothing in M4 needs the hook. It is the live migration's requirement, recorded in "Release ladder", and building it in M4 would have shipped an unexercised feature |
| M4-k | "57 real entries" | 56, and not M4's corpus | Counted in the live manifest. Recorded so the number stops propagating |

Two more corrections, no design impact: the catalogue markers live in `artefacts/index.html`, not the
site homepage; and the site-coupling surface is materially larger than the seven items the
requirement lists: publish/CI topology, the atlas hook, catalogue-shell preexistence, source-mtime
dates and proposal taxonomy are all coupled and all missed.

## Topology

Three state locations, one owner each.

| Where | Holds | Why there |
|---|---|---|
| `~/.claude/skills/artefact-sync/` | code, default page template, bundled `marked.min.js` | `git clone` / `git pull`. No user data, so a reinstall loses nothing |
| `~/.config/artefact-sync/config.json` | `repo`, `source`, `push` | Machine-local. Outside the skill dir so `git pull` cannot clobber it; outside the repo so a second laptop does not inherit your paths |
| `<repo>/artefacts/` | `manifest.json`, `page-template.html`, `index.html`, `vendor/`, the published tree | Travels with the site |

Single target. Re-run `init` to change it.

`cli.py` resolves `(repo_root, source_root, site)` exactly once, before dispatch, into a frozen
`Context` passed to every core function. No function below the CLI resolves a repository or source
path from `~`, `cwd` or `__file__`. Reading `__file__` to find the package's own bundled assets is
exempt: `render.load_template` and `catalogue.render_standalone_catalogue` fall back to
`assets/` when the repo carries no override, and that lookup is relative to the installed skill by
definition.
That is what makes "works from any directory" true rather than aspirational: today
`default_repo_root` derives the repo from the script's own parent, which after extraction points at
the skill directory.

## Schemas

Pointer, `~/.config/artefact-sync/config.json`:

    {"repo": "...", "source": "...", "push": "direct" | "branch"}

Manifest, `<repo>/artefacts/manifest.json`. Existing keys unchanged, one new sibling:

    {version, site, protected_files, ignored_sources, collections, entries}
    site:  {base_url, favicon, catalogue: {mode: "standalone"} | {mode: "inject", page}}
    entry: {id, source, destination, title, collection, order, replacements,
            description?, date?}
    collection: {id, title, description?, section, section_order, order}

`Collection.description` is optional, replacing the prior art's mandatory
`TODO: describe this collection.` placeholder. An absent optional field is omitted from the emitted
JSON rather than written as `null`, or every manifest would churn on its first sync.

`source` is relative to the source root, which lives in the pointer, so the manifest stays
machine-independent. `description` and `date` are new; `Entry` has neither today and
`manifest_from_dict` drops unknown keys, so the current code would silently strip both from the
worked example.

`date` is optional. When absent, the first `sync` stamps it from source mtime and freezes it into the
manifest. Today the catalogue reads mtime live, so re-downloading an unchanged file changes its card
date and reorders the catalogue.

A `dir/` rule matches that directory name at any depth, not only at the root, so shortening a
carried-over rule silently widens it (M4-i).

`ignored_sources` gains `fnmatch` globbing. Matching is currently exact-string or literal `dir/`
prefix, so the requirement's seeded `*.local.*` rule would match nothing and publish the files it was
meant to hide. `init` seeds `prompts/`, `drafts/`, `*.local.*` and dotfiles.

`replacements` survives, documented but unadvertised. It is an ordered raw-text map applied to HTML
only: each key must occur at least once or the run fails, every occurrence is replaced, and later
mappings see text produced by earlier ones.

## Modules

Dependency direction is one-way, so the core is testable with no git, no network and no repo on disk.

    cli.py ──► config.py ──► pointer file, site block
      ├──► scan.py ──► manifest.py
      ├──► propose.py ──► manifest.py
      ├──► plan.py ──► render.py, catalogue.py, scan.py, propose.py
      ├──► apply.py ──► plan.py
      └──► publish.py ──► apply.py, provider.py, git

| Module | Responsibility |
|---|---|
| `config.py` | Pointer and site-block resolution into `Context` |
| `manifest.py` | Schema, validation, order normalisation, HEAD diffing |
| `scan.py` | Source walk, ignore rules, allowlist, SVG validation |
| `render.py` | Markdown page rendering, HTML transformation |
| `catalogue.py` | Standalone shell generation and marker injection |
| `propose.py` | Slug, title and collection derivation for unseen files |
| `plan.py` | Diffing and consequence grouping |
| `apply.py` | Atomic writes, deletions, post-write verification |
| `publish.py` | Preflight, commit, push, build wait, URL verification |
| `provider.py` | `base_url(remote)` and `wait_for_build(commit)`, nothing else |

`propose.py` is the only seam the model touches. It runs solely on sources with no existing entry.
`plan.py` depends on it because `create_sync_plan` cannot classify a vanished source as a rename
without proposing the replacement entry; routing that through `cli.py` would make the CLI
reimplement the reconciliation `plan.py` already owns.

## Commands

`init`, `plan`, `sync`, `add <path>`, `publish`, `validate`.

- `init` writes the pointer; creates `artefacts/` if absent (`manifest.json`,
  `page-template.html`, `vendor/marked.min.js`, a standalone `index.html`); seeds `ignored_sources`;
  guesses `base_url` from the git remote and fetches it once to check the guess. Wholly new.
- `plan` reads and reports, grouped by consequence: new public URLs with byte sizes, changed content
  with diffs, URLs that will start 404-ing, warnings, blocked files. Full URLs, spelled out. Exits 3
  when blocked. It is not a pure read on that one path: a blocked run writes the proposed
  `manifest.json` and nothing else, which is what makes the two-step flow work — the first run
  proposes, the user edits, the second publishes bytes.
- `sync` runs `plan`, confirms, then applies. Atomic per file. Deletes `delete`, never `orphan`. Restores
  missing control files. A pure function of the source folder, which is the property everything else
  rests on.
- `add <path>` copies the file into the source folder, refusing on collision, proposes one
  entry, syncs that entry. Skips the copy when the path is already inside the source folder. Wholly
  new.
- `publish` runs the self-check, `validate`, recompute and apply, irreversibility confirmation, commit,
  push, wait for the build, then fetch every published URL including `protected_files`. Today's URL
  check omits protected files, so a green publish does not prove the vendored JS is reachable.
- `validate` runs offline: expected file set, one catalogue link per entry, local references
  resolve, SVG policy, schema. Orphans warn.

`plan` output:

    NEW PUBLIC URLS (2)
      https://you.github.io/artefacts/talk/cost-model/     14.2 KB
      https://you.github.io/artefacts/talk/curve.png        2.1 MB

    CHANGED (1)
      https://you.github.io/artefacts/incident/q1/         +12 -3 lines

    WILL START 404-ING (1)
      https://you.github.io/artefacts/old-deck.pdf          source deleted

    WARNINGS (3)
      orphan    artefacts/redirect.html    in repo, in no manifest, left alone
      secret    talk/cost-model.html:88    looks like an API key
      external  talk/cost-model.html:12    loads https://unpkg.com/... at runtime

    BLOCKED (1)
      diagrams/flow.svg:42   <script> element

This needs a wider change record than exists today, which carries only a kind and a destination and
so cannot print a URL or a size.

## Safety

Five invariants, each enforced in code rather than left to convention. The first three are new
enforcement, not ported behaviour, and that is where the implementation risk sits.

1. An existing entry is never re-titled or re-slugged. The model proposes only for sources with
   no entry. Enforced by diffing the loaded manifest against `git show HEAD:artefacts/manifest.json`.
2. `destination` is frozen once published. Same diff: a changed `destination` for an existing
   `id` is a hard error naming the URL that would break. Nothing enforces this today: the planner
   silently treats a destination edit as add-new plus delete-old.
3. A source rename keeps its destination. Today the entry is dropped and a fresh destination
   derived from the new filename, so `Deploy Flow.png` → `Deploy Flow v3.png` quietly changes a live
   URL. Detection is content-hash equality against the published bytes, which is exact for a rename
   only where the published bytes ARE the source bytes: the byte-copy formats. A renamed `.md` needs
   its published page's embedded source extracted before comparing, and a renamed `.html` has been
   through `transform_html`, so its published bytes never equal its source. Both fall through to the
   ambiguous case. When hashes do not match, `plan` asks rather than guessing.
4. Orphans are never deleted. `orphan` leaves the deletion set, and `validate` downgrades it to a
   warning. An unmanaged file might be a hand-written page or a redirect.
5. No auto-rollback, no force-push. Every failure stops and prints recovery for that exact state.
   Force-pushing someone's `main` on a transient network error is worse than the failure it cleans up.

Deletions from a vanished source apply with one confirmation for the batch. Secret-shape regexes and
filename heuristics surface as warnings next to the URL. Publishing is irreversible in practice. Search engines cache, and deleting
the file does not undo it. The confirmation says so.

## Rendering

Markdown keeps the client-side mechanism: source embedded verbatim in a `<script type="text/markdown">`
block, rendered by vendored `marked.js`. The invariant is text-exact after UTF-8 decode, line-ending
normalisation and trailing-newline normalisation, not byte-exact: rendering rejects non-UTF-8,
rewrites CRLF and lone CR to LF, and appends a final newline when one is absent. Line endings are
normalised because git with `core.autocrlf=input` stores LF for a CRLF working-tree file, so a page
keeping its CRs is not the page that gets published (M4-b). No test covers a Markdown source missing its final newline; the port adds
one.

`apply` gains a real round-trip check: extract the embedded Markdown, compare to source. Today it
compares rendered bytes to the rendered bytes it just computed, which proves nothing about the round
trip, despite a docstring claiming both the diff preview and `apply`'s byte check depend on it.

The template moves to `artefacts/page-template.html` and switches from `str.format` to
`string.Template`. The current template needs 36 doubled-brace pairs because its CSS is full of
braces; lifted verbatim into a `.html` file it would be neither valid nor previewable. `string.Template`
is stdlib and ignores braces, so nothing needs escaping. Placeholders: `$title`, `$favicon`, `$prefix`,
`$vendor`, `$markdown`, `$block_start`, `$block_end`. `$prefix` is the `../` climb and `$vendor` is the
vendor path alone, so a template composes them as `src="$prefix$vendor"` (M4-a).

`manifest.json`, `index.html` and `page-template.html` are reserved destinations: no entry or
protected file may claim one, or publishing would overwrite the template that renders it.

Catalogue: generate a standalone `artefacts/index.html` by default; if `site.catalogue` names a host
page containing the markers, inject there instead. Standalone generation does not exist today: the
planner cannot run at all in a repo whose catalogue shell is missing. Customising the standalone
catalogue means adding markers to it and switching to inject mode, so there is no second template.
Inject mode reuses the same fragment, so the host page's CSS is what pins the fragment's class names
- `card-grid`, `card`, `card-updated` - and the fragment follows the prior art's markup for exactly
that reason (M4-e).

## File types

Approved: `.html .md .png .jpeg .jpg .ico .pdf .webp .gif .svg`.

The current allowlist is `.html .md .png .jpeg .jpg .ico`. Adding `.pdf`, `.webp` and `.gif` is a
one-line change. `.svg` is gated on the validator in D3.

The cdnjs ban generalises: `plan` warns on any external reference in HTML and blocks none. The
current rule blocks one CDN by raw substring and permits every other remote host, which is theatre.

Closed allowlist, with three distinct outcomes the requirement collapses into one:

- Unsupported extension: summarised by suffix and excluded, no error.
- Ignored: matched an `ignored_sources` rule, excluded, counted.
- Approved but unlisted: stops the run and asks. Only this one blocks.

## Portability

Push via plain `git`, so self-hosted hosts work without a code path. `provider.py` covers only the
two things git cannot do: deriving the public URL from the remote, and waiting for the build. GitLab
Pages URL patterns vary per instance, so `site.base_url` carries the truth and provider detection
only guesses a default; `init` verifies the guess by fetching it once.

The requirement's two-hook claim only survives because of D6. Automating protected-branch PRs would
need PR creation, check polling and merge: six operations through `gh`, GitHub only.

## Testing

160 existing cases. Roughly 110 port with fixture work, 50 are rewritten, 40 are new.

| Area | Cases | Disposition |
|---|---:|---|
| Manifest schema, order normalisation | 27 | Port; add `site`, `description`/`date`, destination-frozen |
| Source inventory, proposals | 31 | Port; replace dirname guard, fallback taxonomy, cdnjs proposal |
| Desired bytes, HTML, Markdown | 36 | Port; re-assert on neutral template; add final-newline case |
| Catalogue | 11 | Port; add standalone generation |
| Plan, apply | 21 | Port; rewrite orphan tests; add grouping, sizes, URLs |
| Unlisted-source flow | 5 | Port; extend for rename-by-hash |
| Repository validation | 9 | Port minus homepage guard and cdnjs; orphans warn |
| Publish | 20 | Rewrite all; every one assumes `gh`, a PR, and a check named `validate` |
| New surface | ~40 | `init`, cwd-independent pointer lookup, `add`, SVG validator, secret scan, self-check, provider |

Unit tests cannot close the publish gap. All 20 publish tests run against a recorded fake world:
they prove orchestration, not that auth, push, build timing, URL derivation or deletion work against
a live host. That is the half changing most, and the disposable repo is its only coverage.

## Release ladder

- M1: portable core, no network. `init`, `plan`, `sync`, `validate` against a local fixture repo.
- M2: disposable GitHub Pages repo. `publish` end to end. The provider seam's only real test.
- M3: `add`, secret warnings, SVG validator, plan output.
- M4: release gate against a disposable probe pair.

M4 is the acceptance test, and it runs against a throwaway repository rather than the live site
(M4-h). Publish a tree with the prior art from a real source folder, copy that template verbatim into
`page-template.html`, seed `date` from current mtimes, install the skill, run `plan`, and require zero
changes. An empty plan proves the extraction preserved behaviour better than any assertion could:
drift in escaping, catalogue rendering, ordering or transformation all show up as a non-empty plan.
It found four such drifts, all fixed in M4. Intentional changes come after that green run. Recorded
in [m4-acceptance.md](m4-acceptance.md).

Migrating `kevinlin.github.io` is a follow-on, not a milestone gate, and it has two unbuilt
prerequisites. First, `site.catalogue.section_links` (M4-j): the prior art injects a 3D showcase link
into the `Image collections` heading, and regenerating that heading deletes it. Second, a home for
the atlas. `build_showcase_atlas.py` is triggered from `apply` and `publish` today and is not ported,
so the site needs it run another way: a git hook, or a step in its own workflow. Otherwise the 3D
showcase goes stale after the first sync. The same read-only comparison M4 ran against the probe was
run against the live tree with those two applied to a scratch copy: all 56 published entry blobs and
`artefacts/index.html` came out byte-identical.

## Consequences accepted

- Strangers get no server-side gate. The last check before content goes public runs on the user's
  laptop and can be skipped. Post-push URL verification is the only proof a publish worked.
- No marketplace means no version number. `manifest.version` has no source of truth, so a future
  schema change arrives with no migration signal.
- `apply` is non-atomic across the tree and can leave it half-written. Survivable because the desired
  tree is a pure function of source plus manifest, so re-running converges, though only for the managed
  tree. Convergence is not established for a failure between apply and push.
- Protected-branch users do the last mile by hand.

## Out of scope

Site scaffolding, `.mp4` and Git-LFS, two-way sync, multiple targets, GitLab as a tested path,
automated PR workflows.
