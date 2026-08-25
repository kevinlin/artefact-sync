# M4 acceptance: the release gate on a prior-art probe tree

Status: offline gate run and passed; live probe pending
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
| Repository | `~/dev/github-kevinlin/artefacts-test`, local for rows 1-12 |
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

## What the run found

Nothing new. Every difference the gate could have surfaced had already been found by the read-only
run that preceded the plan, and each was fixed in Tasks 1-4:

- **`$prefix` and `$vendor` doubled the climb** (Task 1, M4-a). A template using both — as the prior
  art's does — produced `../../../../vendor/marked.min.js`. Every Markdown page would have carried a
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

## Result

The offline gate passed. Thirteen rows, no row failed, no code change was forced, and no published
byte moved.

Rows 14 onwards — installing the skill, creating the public repository, publishing, verifying every
URL, and exercising `.svg`, `.pdf` and a live deletion — are the live probe, and are pending.
