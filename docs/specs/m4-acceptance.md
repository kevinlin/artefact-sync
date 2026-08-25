# M4 acceptance: the release gate on a prior-art probe tree

Status: run and passed
Date: 2026-08-25

The gate ran against a **disposable probe pair**, not the live site. `kevinlin.github.io` was
neither migrated nor modified: the only interaction was copying `scripts/artefacts.py` out of it
once and running that copy from `/tmp` with `python3 -B`, and its `git status --short` printed
nothing before and after every task.

What the gate proves is a comparison, not a corpus. The prior art published a tree from a real
source folder; the skill then adopted that tree and reproduced every published byte of it. Drift in
escaping, catalogue rendering, ordering or transformation would all surface as a moved file, and
none did.

| | |
|---|---|
| Source folder | `~/Downloads/Claude-Artefacts`, read as it stands |
| Repository | `kevinlin/artefacts-test`, public, Pages from `main` / `/ (root)` |
| Published artefacts | `https://kevinlin.github.io/artefacts-test/artefacts/` |
| Entries | 6, in 2 collections, in 1 section |
| Protected files | `vendor/marked.min.js`, `showcase/index.html` |
| Prior-art baseline | commit `2cec156`, "publish via the prior art" |
| Skill adoption | commit `6ed9ee1`, "adopt the artefact-sync skill" |

## The source corpus, as it stood on the day

The folder is real and mutable, so this is the only record of what the gate ran against. It matched
the inventory taken when the plan was written, byte for byte.

```
    31,911  914adf545f413e5d  coding-agent-adoption.html
     1,792  4b2db67d0104453f  mingpt-vs-toy-transformer/analysis.md
 2,130,205  b27c7bc35470172b  mingpt-vs-toy-transformer/infographic.png
     4,414  a2df7bb56c8417f1  mingpt-vs-toy-transformer/prompts/infographic.md
     3,663  f2c5bceae501232f  mingpt-vs-toy-transformer/source-mingpt-vs-toy-transformer.md
     2,718  29d2fee296373266  mingpt-vs-toy-transformer/structured-content.md
    38,189  1e159c345d2ad99a  star-wars-timeline.html
```

Plus two `.DS_Store` files, at the root and in `mingpt-vs-toy-transformer/`, dropped by the walk.
Nine files on disk, seven approved by suffix, one of those ignored, six published.

## Steps

| # | Command | Expected | Result |
|---|---|---|---|
| 1 | Inventory `~/Downloads/Claude-Artefacts` | 7 non-`.DS_Store` files matching the plan's recorded sizes and hashes | Pass. All seven matched exactly, sizes and sha256 prefixes both |
| 2 | Re-check the live corpus, read-only, against the coverage table | 56 entries, 31 collections, 36 protected; 26 `.png`, 14 `.html`, 9 `.md`, 5 `.jpeg`, 2 `.jpg`; 128 approved, 66 after ignores, 10 unlisted | Pass, every figure. Live HEAD had moved from `280b17e` to `4a7880d` since the plan was written, and not one of the figures changed. `git status --short` printed nothing before and after |
| 3 | Create the probe shell: `vendor/marked.min.js`, `showcase/index.html`, host `index.html` with the marker pair, prior-art-schema `manifest.json` with no `site` block | Four files, one commit | Pass. Commit `ea6977d`, `git ls-files` printed exactly those four |
| 4 | Copy `scripts/artefacts.py` to `/tmp/artefacts_prior_art.py` | Copied; the profile repository unchanged | Pass. 88,646 bytes; profile `git status --short` printed nothing |
| 5 | Run the prior art's `apply` twice against the probe, from `/tmp`, with `python3 -B` | Round 1 exits 3 with 6 proposals and writes the manifest; round 2 exits 0, applies, and reports the one ignored source | Pass, both rounds. Round 1: 2 proposed collections, 6 proposed entries, exit 3. Round 2: 6 adds, 2 updates (`index.html`, `manifest.json`), `Ignored sources (1) - mingpt-vs-toy-transformer/prompts/ (1 file)`, exit 0 |
| 6 | Read what it produced | 10 files; 6 entries in 2 collections, both in `Presentations and analysis`; heading id `presentations-and-analysis-heading` | Pass, all three. The collection holding both root-level pages is named `coding-agent-adoption` — the prior art's root-collection naming, the defect M3-b fixed in the skill's proposer. The skill reads this manifest rather than re-deriving it, so nothing diverges |
| 7 | Commit the baseline | Two commits on the probe; profile repository clean | Pass. `2cec156` on top of `ea6977d`; profile printed nothing |
| 8 | Write the adoption prep: convert `MARKDOWN_PAGE_TEMPLATE` for `string.Template`, add a `site` block, write the pointer — all uncommitted | Written, and HEAD's manifest still has no `site` block | Pass. The converted template carries 6 `$` placeholders and no doubled braces |
| 9 | `python3 -m artefact_sync plan` | `CHANGED (1)` naming `manifest.json`, `EXCLUDED (1)`, `WARNINGS (8)`; no new URLs, no 404s, nothing blocked; exit 0 | Pass, exactly. All 8 warnings are off-site references in the two hand-built HTML pages — citation links in the page body, not runtime dependencies. `plan` warns on any external reference by design because it cannot tell the difference |
| 10 | `sync --yes`, then `git diff --name-only HEAD -- artefacts` and a staged `diff --cached --name-status` | Only `artefacts/manifest.json` modified and `artefacts/page-template.html` added | **Pass. This is the gate.** All 6 entry destinations, both protected files and the injected `artefacts/index.html` came out byte-identical to what the prior art committed |
| 11 | Audit the manifest diff | 6 `date` lines added, and otherwise only the `site` block | Pass. Exactly 6 dates; the only other lines were the 7 of the `site` block |
| 12 | `plan` again, then `validate` | No change group at all, exit 0; `validate=0` | Pass. `EXCLUDED (1)` and `WARNINGS (8)` and nothing else, exit 0, `validate=0`. A second run that changes nothing is convergence, which an entry-by-entry byte comparison cannot show |
| 13 | Commit the adoption on the probe | One commit, two files; profile repository clean | Pass. `6ed9ee1`, `artefacts/manifest.json` and `artefacts/page-template.html`, 238 insertions; profile printed nothing |
| 14 | Symlink the skill into `~/.claude/skills/`, then `gh repo create kevinlin/artefacts-test --public --source --push` | Repository created and pushed | Pass. A symlink rather than a clone, so the gate tests the code about to be tagged rather than a copy of it. `main` pushed and tracking |
| 15 | Enable Pages, `main` / `/ (root)`, and wait for the first build | Built and serving | Pass, and done through `gh api repos/.../pages -X POST` rather than the settings UI — one call, same result. `building` then `built`; the artefacts URL went 404 to 200 in under 20 seconds |
| 16 | `python3 -m artefact_sync init --repo ... --source ...` | Pointer written, `artefacts/` seeded, base URL verified | Pass. `verified https://kevinlin.github.io/artefacts-test/artefacts/`. `init` creates nothing that already exists: the manifest, the template and the vendored JS were all left alone, and `git diff --name-only HEAD -- artefacts` printed nothing |
| 17 | `time python3 -m artefact_sync publish` | Nothing left to apply, 10 URLs verified | Pass. `nothing to publish; 10 published URLs verified.` in **4.0 seconds** — the base URL, `index.html`, 6 entries and 2 protected files. M2's 39 seconds included a push and a build wait; this run had neither |
| 18 | Fetch the published pages and assert on what M4's four fixes changed | Catalogue carries `card-grid` / `card` / `card-updated`; the showcase page untouched; the Markdown page loads `../../vendor/marked.min.js` and carries `id="markdown-source"` and the newline strip | Pass, all of it. `../../vendor/marked.min.js` from depth 2 resolves to a 200 of 39,903 bytes, which is Task 1's `$prefix$vendor` fix proving itself live. Both hand-built HTML pages kept their literal `</script>`, em dashes and entities |
| 19 | Compare served bytes against source bytes for the byte-copy formats | `same` for the 2 MB PNG | Pass. `same  mingpt-vs-toy-transformer/infographic.png  2,130,205 bytes`. A 2 MB image round-tripping intact through push and Pages closes by hand the gap the design records as "nothing verifies that the bytes GitHub serves equal the bytes pushed" |
| 20 | Add `flow.svg` and `brief.pdf` to the source folder, then `plan` | Exit 3, `BLOCKED (2)` naming both as approved-but-unlisted, `NEW PUBLIC URLS (2)` with sizes | Pass. Exit 3; `brief.pdf  69 B` and `flow.svg  185 B`. A closed allowlist stopping to ask about two files the user just added is correct behaviour, and it is the two-step flow M3 built |
| 21 | Review the proposed entries, then `publish` | Confirmation names both new URLs and the irreversibility; 12 URLs verified | Pass. Both root-level files landed in the `coding-agent-adoption` collection — the prior art's root-collection naming, inherited from the adopted manifest rather than re-derived. `published 50947864e8b4 on main`, `verified 12 published URLs` |
| 22 | Fetch the two new URLs | Both serve; the SVG renders | Pass. `flow.svg` HTTP 200 `image/svg+xml` 185 bytes and byte-identical to source; `brief.pdf` HTTP 200 `application/pdf` 69 bytes. The catalogue links all 8 entries |
| 23 | Add a `dirty.svg` carrying a `<script>` element, then `plan` | `BLOCKED` naming the file and line, exit 3, nothing published | Pass on the gate, with a correction to the expectation. `dirty.svg:2   script element ('<script')`, exit 3, and no published file written. The plan's step said "nothing written"; a blocked run does write the proposed `manifest.json`, which is `plan`'s documented behaviour and what makes the two-step flow work. Reverted with `git checkout` after removing the file |
| 24 | Delete `brief.pdf` from the source folder, then `publish` | Confirmation says exactly one URL will start 404-ing; afterwards it 404s and the others serve | Pass. `WILL START 404-ING (1)` naming `brief.pdf` and nothing else; `published 4550825341ba on main`, `verified 11 published URLs`. Afterwards `brief.pdf` returns 404, `flow.svg`, the 2 MB PNG and `showcase/index.html` all return 200, and the catalogue dropped the link. **No orphan warning named the file being deleted** — that is M3's fix holding on a live run, and it is the defect M2 row 10 found |
| 25 | `publish` again with nothing changed | `nothing to publish`, every URL re-verified, no commit | Pass. `nothing to publish; 11 published URLs verified.`, no new commit |

## What the run found

Nothing new. Every difference the gate could have surfaced had already been found by the read-only
run that preceded the plan, and each was fixed in Tasks 1-4:

- **`$prefix` and `$vendor` doubled the climb** (Task 1, M4-a). A template using both, as the prior
  art's does, produced `../../../../vendor/marked.min.js`. Every Markdown page would have carried a
  broken `<script src>`.
- **Line endings were never normalised** (Task 1, M4-b). With `core.autocrlf=input`, the tree
  `apply` wrote was not the tree git stored, so a fresh clone would report the same entry CHANGED
  forever.
- **The embedded block id and its leading newline** (Task 2, M4-c). Every page the prior art
  published carries `id="markdown-source"` and a newline; keeping the skill's spelling would have
  rewritten all of them, and `extract_markdown` could not have read any.
- **The catalogue emitted its own markup and sorted entries by date** (Task 3, M4-d, M4-e). The host
  page's CSS targets `card-grid`, `card` and `card-updated`; the prior art sorts *cards* by date and
  *entries* by `order`.
- **`head_manifest` failed on a pre-`site` HEAD** (Task 4, M4-f). Not a rendering defect but an
  adoption blocker: the first command in any adopting repository exited with `missing manifest
  field: site`, naming a field the user had already set in the working copy. Row 9 ran against
  exactly that HEAD, which is what makes this row evidence rather than a unit test.

The gate's own limit is scale: 6 entries against the live site's 56. Row 2 is how that was checked —
the same read-only comparison against the live corpus, re-run, with every figure unchanged.

The live rows added two observations the offline gate could not:

- **`validate` sees external references the plan does not.** Publishing surfaced Google Fonts
  references at lines 9-11 of every rendered Markdown page. They come from the adopted template,
  whose own page template loads Inter from `fonts.googleapis.com`, not from any source file. `plan`
  never mentions them and `validate` does. Both work as designed: `plan` scans sources, `validate`
  scans the published tree. Worth knowing before an adopter reads the two
  outputs side by side and assumes one is wrong.
- **A blocked `plan` writes the proposed manifest, by design.** Row 23 expected "nothing written".
  Nothing *published* is written, which is the safety claim; the proposal is written, which is what
  the two-step flow needs. The plan's wording was wrong, not the code.

## Teardown

Kept, deliberately. The next milestone gets a live target for free, and deleting the repository
needs an interactive `gh auth refresh -h github.com -s delete_repo` first, as M2 found.

- **`kevinlin/artefacts-test` kept**, public, serving 11 URLs.
- **`~/Downloads/Claude-Artefacts` holds one added file**, `flow.svg`. `brief.pdf` was added and
  then deleted by row 24; `dirty.svg` was added and removed inside row 23. The other nine files are
  exactly as row 1 recorded them.
- **The skill symlink at `~/.claude/skills/artefact-sync` kept**, pointing at the working tree.
- **The pointer at `~/.config/artefact-sync/config.json` kept**, aimed at the probe pair.
- **`kevinlin.github.io` untouched**, verified clean after every task.

To remove what is left:

    rm ~/Downloads/Claude-Artefacts/flow.svg
    rm ~/.claude/skills/artefact-sync
    gh auth refresh -h github.com -s delete_repo && gh repo delete kevinlin/artefacts-test --yes

## Result

Passed. Twenty-five rows, no row failed, and no code change was forced by the run.

Row 10 is the milestone: **no published byte moved.** All 6 entry destinations, both protected files
and the injected catalogue came out byte-identical to what the prior art committed, from a source
folder neither implementation was written against. Row 12 adds convergence, which a byte comparison
cannot show. Together they are the extraction proof the design asked M4 for, on a repository nobody
has shared a URL from.

What the live rows cover that the 246 unit tests cannot: real Pages hosting of a tree the prior art
built, a 2 MB image compared byte for byte after a round trip through push and Pages, a live 404
from a real deletion with no orphan warning misnaming it, and the `.svg` and `.pdf` paths the prior
art has no counterpart for — including an SVG rejected by line number rather than rewritten.

One check is outstanding and is a human's to make: opening the catalogue, a Markdown page and a
hand-built HTML page in a real browser to confirm they render and the console is quiet. Everything
machine-checkable about those pages passed in row 18.
