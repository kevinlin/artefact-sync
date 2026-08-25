# artefact-sync M4 Implementation Plan

**Goal:** Close the release gate on a disposable probe pair — the real source folder
`~/Downloads/Claude-Artefacts` publishing to `https://kevinlin.github.io/artefacts-test/artefacts/` —
by proving the skill reproduces, byte for byte, a published tree the prior art generated from that
same folder. `kevinlin.github.io` is not migrated and not modified.

**Architecture:** No new modules. M4 is four small corrections inside `render.py`, `catalogue.py`
and `manifest.py`, then a fixture and a gate. The fixture is the load-bearing idea: a throwaway
repository whose `artefacts/` tree is published by `scripts/artefacts.py` — run from a copy, against
`--repo`/`--source` pointing at the probe — and committed. The skill then adopts that tree. Zero
rewrites is the gate. All four corrections are measured, not guessed: with them applied to a scratch
copy, all 6 probe entries and the injected catalogue come out identical to the prior art's committed
bytes, and a commit would carry only `artefacts/manifest.json` and `artefacts/page-template.html`.

**Tech Stack:** Python 3.9, standard library only, `unittest`. Tasks 1-7 run offline. Task 8 touches
GitHub and the network.

**Spec:** [design_artefact-sync.md](design_artefact-sync.md), release ladder line "M4: release gate",
and the "Release ladder" section's M4 paragraph. Supporting evidence with `file:line` citations into
the prior art is [extraction-analysis.md](../research/extraction-analysis.md). The three earlier
milestones and the deviations this plan inherits are
[plan_artefact-sync-m1.md](plan_artefact-sync-m1.md),
[plan_artefact-sync-m2.md](plan_artefact-sync-m2.md),
[plan_artefact-sync-m3.md](plan_artefact-sync-m3.md), and M2's live evidence is
[m2-acceptance.md](m2-acceptance.md).

---

## What M4 actually is

The design's ladder line reads "M4: release gate, migrating `kevinlin.github.io`", and the "Release
ladder" section spells out the procedure: publish with the prior art, install the skill, run `plan`,
require zero changes. That procedure was run against the live tree, read-only, before this plan was
written. It found four defects, all in the skill, each of which silently rewrites published content.

| # | What breaks | Effect | Task |
|---|---|---|---|
| 1 | `render_markdown_page` bakes the `../` climb into `$vendor`, and the design's template also uses `$prefix`, so a template using both — as the prior art's does — doubles the climb | Every Markdown page gets a broken `<script src>`; `validate` catches it as `broken local reference` | 1 |
| 2 | Neither `render_markdown_page` nor `transform_html` normalises line endings, and `core.autocrlf=input` strips CR on commit, so the tree `apply` writes is not the tree git stores | Any CRLF source. A fresh clone never converges: `plan` reports the same entry CHANGED forever | 1 |
| 3 | The embedded block is `id="artefact-source"` with no leading newline; every page the prior art published carries `id="markdown-source"` and a newline | Every Markdown page rewritten for no reason. `extract_markdown` also cannot read a page the prior art published, so `plan` prints `diff unavailable: page has no embedded Markdown` instead of a diff | 2 |
| 4 | `catalogue.render_catalogue` emits its own markup and sorts entries by date; the prior art's host page CSS targets `card-grid`, `card` and `card-updated`, and sorts *cards* by date and *entries* by `order` | The whole catalogue replaced with unstyled markup, card and entry order shuffled | 3 |

Plus one adoption blocker that is nobody's defect but stops the first run dead:

| # | What breaks | Task |
|---|---|---|
| 5 | `manifest.head_manifest` parses `git show HEAD:artefacts/manifest.json` through the full strict schema, so in any repository whose committed manifest predates the `site` block the first command exits with `missing manifest field: site` — naming a field the user has already set in the working copy | 4 |

### Why a probe, and what that costs

The design names `kevinlin.github.io` as the gate. This plan uses a disposable pair instead, because
the gate's value is the comparison, not the corpus: what proves the extraction is *the prior art
published this tree, and the skill reproduces it exactly*. A probe seeded by `scripts/artefacts.py`
makes that comparison on a repository nobody has shared a URL from.

The source folder is real, not generated. `~/Downloads/Claude-Artefacts` is a staging folder of
Claude-produced artefacts, with the same shapes the live corpus has: nested collection directories,
root-level pages, a `prompts/` working directory, `.DS_Store` litter, and two large hand-built HTML
pages full of the escaping that breaks naive round trips.

**What the corpus covers.** 9 files, 7 approved by suffix, 6 published entries in 2 collections.
Markdown pages through the embed-and-extract round trip; two 30-40 KB HTML pages carrying literal
`</script>`, em dashes, entities and off-site references; a 2 MB PNG as a byte copy; a `prompts/`
directory matched by an ignore rule; `.DS_Store` dropped by the walk; and directory-index
destinations at two depths, which is what makes the `$prefix` defect visible.

**What it does not cover, and where those stay covered.** Measured, not assumed:

| Not in the corpus | Covered instead by |
|---|---|
| A CRLF text source | Task 1's unit tests, and Task 5's `test_m4_adoption.py`, which drives a CRLF source through a real git repository under this machine's real `core.autocrlf` |
| A file with no final newline | Task 1's unit tests, and the existing `test_a_source_without_a_final_newline_gains_one` |
| An unsupported suffix, so `EXCLUDED` shows only the ignored outcome | `tests/test_scan.py`, and M2's live run, which reported `.psd` and friends |
| A dotfile directory, so the `.*` seed rule is unnecessary here | `tests/test_scan.py::test_dotfiles`, and the live measurement in Task 6 Step 1 |
| A secret-shape line or a private-looking filename | `tests/test_secrets.py`, 8 cases |
| `replacements` | Unit tests only. No live entry uses it either |
| An `Image collections` section, so the prior art emits no showcase link | Nothing, deliberately. See M4-j |

### The probe pair

| | |
|---|---|
| Source folder | `~/Downloads/Claude-Artefacts`, read as it stands |
| Repository | `kevinlin/artefacts-test`, public, Pages from `main` / `/ (root)` |
| Published artefacts | `https://kevinlin.github.io/artefacts-test/artefacts/` |
| Entries | 6, in 2 collections, in 1 section |
| Protected files | `vendor/marked.min.js`, `showcase/index.html` |
| URLs `publish` verifies | 10 — the base URL, `index.html`, 6 entries, 2 protected files |

---

## Corrections to the design this plan applies

Each was found by running the skill against a real published tree. Apply each to
[design_artefact-sync.md](design_artefact-sync.md) as M1, M2 and M3 did.

| # | What the design or the code says | What M4 does | Why |
|---|---|---|---|
| M4-a | Template placeholders are `$title, $favicon, $prefix, $vendor, ...` | `$vendor` is the vendor path alone; `$prefix` is the `../` climb; the shipped template composes `src="$prefix$vendor"` | `render_markdown_page` passes `vendor=prefix + vendor_path`, and the shipped template uses `$vendor` on its own, so the two placeholders cannot both be used as documented. A template using both, as the prior art's does, produces `../../../../vendor/marked.min.js` |
| M4-b | E5: the invariant is "text-exact after UTF-8 decode and trailing-newline normalisation" | Text-exact after UTF-8 decode, **line-ending normalisation**, and trailing-newline normalisation | Git with `core.autocrlf=input` — the setting on this machine, and a common default — stores LF for a CRLF working-tree file. Without normalisation the bytes `apply` writes are not the bytes that get published, and a fresh clone reports the same entry CHANGED on every run, forever. Normalising CRLF to LF is safe for Markdown: a hard line break is trailing spaces or a backslash, never a CR |
| M4-c | The Markdown block is `<script type="text/markdown" id="artefact-source">` | `<script type="text/markdown" id="markdown-source">` followed by a newline | That is what the prior art published (`artefacts.py:525-526`). Keeping the skill's spelling rewrites every Markdown page an adopter has, and `extract_markdown` cannot read any of them, so the diff preview and `apply`'s round-trip check both go blind on exactly the pages an adoption needs to check |
| M4-d | "`date` lets the catalogue sort by recency instead of hand-maintained `order`" | Collection **cards** sort by their newest entry date, descending, stable on `order`. **Entries** inside a card keep sorting by `order` | The prior art sorts cards by recency and entries by `order` (`artefacts.py:1360-1383`). Sorting entries by date too reorders any curated collection, and it is the wrong reading anyway: a card's date answers "is this collection fresh", while an entry's position inside a card is editorial |
| M4-e | "Customising the standalone catalogue means adding markers to it and switching to inject mode, so there is no second template" | True for the shell, false for the fragment. `render_catalogue` adopts the prior art's markup | The fragment's class names are what the host page's CSS targets, so a host page cannot adopt a foreign fragment without a rewrite. Making the tool's markup the prior art's is what lets any existing inject-mode page keep its stylesheet |
| M4-f | `head_manifest` returns "the manifest as of HEAD, or None when it was never committed" | Also `None` when HEAD's manifest cannot be parsed, after one attempt with a placeholder `site` injected | A repository adopting the skill has a committed manifest with no `site` block, and the invariant check reads only `id`, `destination` and `title` from it. Failing the whole run on a field the check never touches makes adoption impossible; returning `None` immediately would throw away the URL-freeze guard on precisely the run where published destinations are at stake. Injecting a placeholder keeps the guard |
| M4-g | `HOMEPAGE_FILES` is part of the site-coupling surface still to port | Not ported | It backs a `git diff --exit-code base...HEAD -- index.html styles.css script.js` check. `publish`'s preflight already refuses any change outside `artefacts/`, which is strictly stronger and needs no base ref |
| M4-h | M4 is "the release gate, migrating `kevinlin.github.io`", and the migration "has to rehome the atlas" | The gate runs against a disposable probe pair. `kevinlin.github.io` is untouched, so its `scripts/artefacts.py`, its `validate-artefacts.yml` and its atlas hook all stay exactly as they are | Deferred by the milestone's owner. The extraction proof does not need the live site's URLs at risk, and the fixes this milestone lands are most of what makes the live migration a no-op whenever it is taken. D1 still stands as the eventual destination; it is no longer this milestone's gate |
| M4-i | `ignored_sources` matching "is currently exact-string or literal `dir/` prefix", widened by E3 to `fnmatch` | Recorded as a migration hazard, with a test. A bare `name/` rule matches that directory **at any depth** in the skill; in the prior art it matches only at the root | Found by the probe corpus: `prompts/` ignores `mingpt-vs-toy-transformer/prompts/infographic.md` under the skill and nothing under the prior art. The skill's behaviour is deliberate (`manifest.is_ignored` checks `directory in source.parts[:-1]`) and better, but a manifest carried over from the prior art can start ignoring files it used to publish, and those show up as deletions. The live manifest happens to be safe because all three of its `prompts/` rules carry full prefixes |
| M4-j | (not addressed) | `site.catalogue.section_links` is **not** built | The prior art injects a 3D showcase link into the `Image collections` heading unconditionally, and regenerating that heading would delete it. The probe corpus produces one section and no such link, so nothing in this milestone needs the hook. It is the live migration's requirement, recorded with its measurement in "After M4", and building it now would ship an unexercised feature into a milestone whose scope was deliberately narrowed |
| M4-k | "57 real entries" (requirement and design) | 56, and not this milestone's corpus | Counted in the live manifest. Recorded so the number stops propagating |

---

## Task status

Complete, 2026-08-25. All 47 steps ran; evidence in [m4-acceptance.md](m4-acceptance.md).

| Task | Status | Commit | Tests after |
|---|---|---|---:|
| 1. Newline-normalising decode, `$vendor` means the vendor path | Done | `0acef4c` | 232 |
| 2. The embedded block matches what the prior art published | Done | `4bf9102` | 233 |
| 3. The catalogue emits markup a host page can style | Done | `4f58e3e` | 240 |
| 4. `head_manifest` survives a HEAD predating the `site` block | Done | `5b0cab9` | 242 |
| 5. Adoption proof, ignore-rule hazard, `SKILL.md` | Done | `cb711b7` | 246 |
| 6. The fixture: a probe tree the prior art published | Done | probe `2cec156` | 246 |
| 7. The gate: the skill reproduces it byte for byte | Done | `6800abc`, probe `6ed9ee1` | 246 |
| 8. The live probe: publish, verify, `.svg` and `.pdf` | Done | `2592419` | 246 |

246 tests pass on both `python3` (3.13) and `/usr/bin/python3` (3.9.6). The gate result: no
published byte moved. See "Deviations from this plan" for the six places the plan was wrong.

---

## Implementation Tasks

### Task 1: newline-normalising decode, and `$vendor` means the vendor path

Added `render.normalise_source_text(source_bytes, label)` — decodes UTF-8, rewrites `\r\n` and lone `\r` to `\n`, guarantees a trailing newline. Routed `render_markdown_page`, `transform_html` and `apply.verify_markdown_round_trip` through it. Changed `$vendor` to carry only the vendor path (`vendor/marked.min.js`), so the shipped template composes `src="$prefix$vendor"`. Five new tests across `test_render_markdown.py`, `test_render_html.py` and `test_apply.py`.

### Task 2: the embedded block matches what the prior art published

Changed `render.BLOCK_START` to `<script type="text/markdown" id="markdown-source">\n` — the id and leading-newline shape every page the prior art published. Updated the shipped template's reader script to strip that leading newline from `textContent`. Three new tests in `test_render_markdown.py`, one literal update in `test_apply.py`.

### Task 3: the catalogue emits markup a host page can style

Rewrote `catalogue.render_catalogue` to emit the prior art's markup (`card-grid`, `card`, `card-updated` classes), sort cards by newest-entry date descending (stable on `order`), and sort entries within a card by `order` only. Added `catalogue.section_slug`. Removed `_invert` and `entry_sort_key`. Restyled `catalogue-template.html`. Replaced `SortTests` with `MarkupTests`, `CardOrderTests` and `EntryOrderTests` — ten tests total.

### Task 4: `head_manifest` survives a HEAD predating the `site` block

Made `head_manifest` lenient: injects a placeholder `site` block before validating, returns `None` on any parse failure. This keeps the URL-freeze guard working during adoption without failing on a field it never checks. Two tests in `test_manifest_invariants.py::AdoptionTests`.

### Task 5: adoption proof, ignore-rule hazard, and `SKILL.md`

Created `tests/test_m4_adoption.py` proving a published tree survives re-adoption unrewritten (including the CRLF path the probe corpus lacks). Pinned the `dir/`-matches-at-any-depth hazard in `tests/test_scan.py`. Added "Adopting an existing artefacts tree" to `SKILL.md`.

### Task 6: the fixture — a probe tree the prior art published

Created the `kevinlin/artefacts-test` repository shell, ran `scripts/artefacts.py` against `~/Downloads/Claude-Artefacts` to produce 6 entries in 2 collections, and committed the baseline. No code in this repository changed.

### Task 7: the gate — the skill reproduces it byte for byte

Ran the adoption procedure against the probe: wrote `page-template.html` and the `site` block, ran `plan` and `sync`. Result: only `manifest.json` (date stamps) and `page-template.html` (new file) differ from HEAD; all 6 entry destinations, both protected files and the injected catalogue are byte-identical. Wrote [m4-acceptance.md](m4-acceptance.md) and applied corrections M4-a to M4-k to [design_artefact-sync.md](design_artefact-sync.md).

### Task 8: the live probe — publish, verify, `.svg` and `.pdf`

Published to GitHub Pages, verified 10 URLs, confirmed served bytes match source bytes for the 2 MB PNG. Added `flow.svg` and `brief.pdf` through the two-step propose-then-publish flow. Proved the SVG validator rejects `dirty.svg:2` with `script element`. Exercised a deletion and reconverged at 11 verified URLs.

---

## Critical Files — Summary

| Path | M4's change |
|---|---|
| `artefact_sync/render.py` | `normalise_source_text`, `BLOCK_START` gains the prior art's id and newline, `$vendor` loses the baked-in prefix |
| `artefact_sync/apply.py` | Round-trip verification normalises the source the same way the renderer does |
| `artefact_sync/catalogue.py` | Prior-art markup, `section_slug`, cards by date and entries by order |
| `artefact_sync/manifest.py` | `head_manifest` tolerates a HEAD manifest predating the `site` block |
| `artefact_sync/assets/page-template.html` | `src="$prefix$vendor"`, `markdown-source`, leading-newline strip |
| `artefact_sync/assets/catalogue-template.html` | CSS matches the new fragment markup |
| `SKILL.md` | "Adopting an existing artefacts tree" |
| `docs/specs/m4-acceptance.md` | The fidelity gate and the live probe publish |

---

## Deviations from this plan

Recorded because the plan was written before the code existed, and a plan that hides where it was
wrong is worth less on the next milestone.

**Status: implemented and accepted, 2026-08-25.** All eight tasks ran. The suite is 246 tests,
passing on both `python3` (3.13) and `/usr/bin/python3` (3.9.6). Evidence is
[m4-acceptance.md](m4-acceptance.md), 25 rows, none failed.

**Every predicted test count was right.** 227 at the start, then 232, 233, 240, 242, 246: the
figures in "Predicted counts", unaltered, with no test renamed or merged to reach them. So was every
predicted failure message, including Task 4's two `ValidationError` texts verbatim.

Six places the plan was wrong. None changed the design, and none needed a code change.

| # | Plan said | What happened |
|---|---|---|
| 1 | Task 3 Step 2: "every new `MarkupTests`, `CardOrderTests` and `EntryOrderTests` case fails" | Seven of ten failed. `test_an_undated_card_says_nothing_about_dates`, `test_titles_are_escaped` and `test_cards_sharing_a_date_keep_their_declared_order` passed against the old markup. The first two assert on absence, the third on an order the old code already produced by a different route. All ten pass against the new markup, which is what they are for |
| 2 | Task 6 Step 1: "a different list is not a failure; the folder is real and may have moved on" | It had not moved. All seven files matched the recorded sizes and hashes exactly, and the live corpus figures were unchanged too, despite live HEAD advancing from `280b17e` to `4a7880d` |
| 3 | Task 7 Step 8: correct "57 real entries" to 56 "there and in `Testing`" | The design's `Testing` section never carried the number; only the release ladder did. Corrected there. The requirement document still says 57 and was out of this milestone's scope to edit. M4-k records the count so it stops propagating |
| 4 | Task 8 Step 1: enable Pages through Settings, Pages, by hand | Done with one `gh api repos/kevinlin/artefacts-test/pages -X POST -f 'source[branch]=main' -f 'source[path]=/'`. Same result, no UI, and it makes the step reproducible |
| 5 | Task 8 Step 2: "Record the wall-clock time against M2's 39 seconds for 6 URLs" | 4.0 seconds for 10 URLs, but the comparison does not hold: M2's 39 seconds included a push and a Pages build wait, and this run had nothing to push. The publish that *did* push (row 21) is the comparable one |
| 6 | Task 8 Step 5: the `dirty.svg` run leaves "nothing written" | Nothing *published* is written, which is the safety claim. The proposed `manifest.json` is written, because a blocked `plan` writing its proposal is what makes the two-step flow work; the design says so under `plan`. The expectation was wrong, not the code. Reverted with `git checkout` after removing the file |

One thing the live rows found that no task predicted: `validate` reports Google Fonts references at
lines 9-11 of every rendered Markdown page, and `plan` reports none of them. They come from the
adopted template, not from any source file. `plan` scans sources, so it cannot see them; `validate`
scans the published tree, so it can. Both are working as designed. It is recorded in
the acceptance document because an adopter reading the two outputs side by side will otherwise
assume one is broken.

---

## After M4

- **Migrating `kevinlin.github.io` is available and measured.** The same procedure Task 7 runs
  against the probe was run read-only against the live tree while this plan was written, with the
  four fixes plus a `section_links` hook applied to a scratch copy: all 56 published entry blobs and
  `artefacts/index.html` came out byte-identical, and a commit would carry only
  `artefacts/manifest.json` and `artefacts/page-template.html`. That migration needs two things this
  milestone does not build. First, `site.catalogue.section_links` (M4-j), because the prior art
  injects a 3D showcase link into the `Image collections` heading and regenerating that heading
  deletes it. Second, a home for `build_showcase_atlas.py`, which fires from the prior art's `apply`
  and is not ported, so it has to become a documented manual step before the first sync that adds or
  removes a published image.
- **`manifest.version` still has no source of truth.** M4 changed `BLOCK_START`, and that carries no
  migration signal. Someone adopting a pre-M4 tree gets no warning that the block id moved; they find
  out from a non-empty plan, which is how M4 found everything.
- **`publish` still checks status codes, not bytes.** Task 8 Step 4 compares served bytes against
  source bytes by hand for the byte-copy formats. Folding that into `publish` is the obvious next
  guard, and M4 found a real case where git changed the bytes between apply and push.

---

## Changelog

- 2026-08-25 — **Compacted post-implementation.** Removed step-by-step tasks, file-by-file diffs, code snippets, verification commands, global constraints, self-review prose, and warnings section now that the feature has shipped. Preserved Goal, Architecture, Corrections, Task status table, Critical Files summary, Deviations, and After M4. Original plan recoverable via git history.
