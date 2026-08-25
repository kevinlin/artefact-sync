# artefact-sync M4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

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

## Global Constraints

Every task's requirements implicitly include this section. The first ten carry over from M3.

- **Python 3.9.** The tool must run under stock macOS `/usr/bin/python3` (3.9.6). Every module
  starts with `from __future__ import annotations` so `X | None` annotations parse on 3.9.
- **Standard library only.** No third-party import in the shipped package or in its tests, ever.
  `tests/test_stdlib_only.py` already allows every module M4 needs (`re`, `string`, `json`);
  do not widen `ALLOWED`.
- **Test command:** `python3 -m unittest discover -s tests -t . -v`. Never pytest. Run it under
  **both** `python3` (3.13) and `/usr/bin/python3` (3.9.6) before every commit.
- **The M3 baseline is 227 tests, all passing on both interpreters.** No task may leave that number
  lower.
- **British spelling** in every user-facing string, path and identifier: `artefacts`, `catalogue`.
- **No emoji** in any output. `tests/test_plan.py::test_no_emoji_anywhere_in_the_output` enforces it
  for `format_plan`; keep it passing.
- **The shipped assets carry no branding.** `tests/test_render_markdown.py`
  ::`test_the_shipped_template_carries_no_branding` forbids `kevin`, `kevinlin` and `github.io` in
  `artefact_sync/assets/page-template.html`. M4 converts the prior art's template into the *probe*
  repository, never into `assets/`. Keep that test passing.
- **Exit codes:** `0` success, `1` error, `3` blocked and needs a human decision.
- **No network in the unit suite.** Tasks 1-7 add no networked code path.
- **`/Users/keli/dev/github-kevinlin/kevinlin.github.io` is read-only for the whole milestone.** Not
  migrated, not edited, no branch, no commit. The only interaction is copying `scripts/artefacts.py`
  out of it once, in Task 6, and running that copy from elsewhere with `python3 -B` so no bytecode is
  written back. Every task ends with `git -C /Users/keli/dev/github-kevinlin/kevinlin.github.io
  status --short` printing nothing.
- **`~/Downloads/Claude-Artefacts` is the gate's source folder, and it is real.** Tasks 6 and 7 only
  read it. Task 8 adds two files to it and deletes one temporary file, all named in its steps and
  all removable afterwards. Nothing else in it is created, edited or deleted.
- **`git status` is not the gate; `git diff HEAD` is.** With `core.autocrlf = input` — set in
  `~/.gitconfig` on this machine — `git status` reports a file whose working-tree line endings
  changed, even when the content diff against HEAD is empty. Use
  `git diff --name-only HEAD -- artefacts` and `git diff --cached --name-status` for every assertion
  about what moved.
- **Every test count in this plan is a prediction.** M2 and M3 both recorded cases where a stated
  count was satisfied by contorting the code instead of correcting the number. If your count
  differs, the number here is wrong: fix it in "Deviations from this plan". Never merge two distinct
  failures into one `subTest` loop, and never build a test name by string concatenation, to hit a
  figure written before the code existed.

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
pages full of the escaping that breaks naive round trips. Its content is what it is, which is the
point and also the limit.

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

Scale is the other gap: 6 entries against the live site's 56. A rendering path that appears once in
fifty real files could hide. The live measurements the corpus was checked against are in Task 6
Step 1, and re-running the read-only comparison there is how you check whether that matters.

### The probe pair

| | |
|---|---|
| Source folder | `~/Downloads/Claude-Artefacts`, read as it stands |
| Repository | `kevinlin/artefacts-test`, public, Pages from `main` / `/ (root)` |
| Published artefacts | `https://kevinlin.github.io/artefacts-test/artefacts/` |
| Entries | 6, in 2 collections, in 1 section |
| Protected files | `vendor/marked.min.js`, `showcase/index.html` |
| URLs `publish` verifies | 10 — the base URL, `index.html`, 6 entries, 2 protected files |

The repository root URL the pair is named for, `https://kevinlin.github.io/artefacts-test/`, serves
the repository's own root; the skill publishes one level down under `artefacts/`, exactly as it does
for any project-page repository. M2's probe had the same shape.

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

## File Structure

```
artefact-sync/
  SKILL.md                          + "Adopting an existing artefacts tree"
  artefact_sync/
    render.py                       + normalise_source_text, BLOCK_START, vendor placeholder
    apply.py                        verify_markdown_round_trip uses normalise_source_text
    catalogue.py                    prior-art markup, section_slug, card ordering
    manifest.py                     head_manifest tolerates a pre-site HEAD manifest
    assets/page-template.html       src="$prefix$vendor", markdown-source, leading-newline strip
    assets/catalogue-template.html  CSS renamed to .card-grid / .card / .card-updated
  tests/
    test_render_markdown.py         + CRLF cases, block-id cases rewritten
    test_render_html.py             + CRLF case
    test_apply.py                   + CRLF round trip, block-id literal updated
    test_catalogue.py               SortTests replaced by MarkupTests / CardOrderTests /
                                    EntryOrderTests
    test_scan.py                    + a bare directory rule matches at any depth
    test_manifest_invariants.py     + a HEAD manifest with no site block
    test_m4_adoption.py    NEW      adopting a tree that already has published files
  docs/specs/
    m4-acceptance.md       NEW      the fidelity gate and the live probe publish, recorded
    plan_artefact-sync-m4.md        this file: status line and deviations, at the end
    design_artefact-sync.md         corrections M4-a to M4-k
```

`config.py` is untouched: M4-j drops the only change it would have taken.

Dependency direction is unchanged. No module gains an import.

---

## Implementation Tasks

### Task 1: one newline-normalising decode, and `$vendor` means the vendor path

**Files:**
- Modify: `artefact_sync/render.py` (add `normalise_source_text`; use it in `render_markdown_page`
  and `transform_html`; drop the prefix from the `vendor` substitution)
- Modify: `artefact_sync/apply.py:48-62` (`verify_markdown_round_trip`)
- Modify: `artefact_sync/assets/page-template.html` (the `<script src>` line)
- Test: `tests/test_render_markdown.py`, `tests/test_render_html.py`, `tests/test_apply.py`

**Interfaces:**
- Consumes: `render.render_markdown_page`, `render.transform_html`, `render.extract_markdown`,
  `apply.verify_markdown_round_trip`, `manifest.Entry`, `config.site_from_dict`.
- Produces: `render.normalise_source_text(source_bytes: bytes, label: str) -> str` — decodes UTF-8,
  rewrites `\r\n` and lone `\r` to `\n`, and appends a final `\n` to non-empty text. Raises
  `TransformationError` naming `label` on invalid UTF-8. Called by `render_markdown_page`,
  `render.transform_html` and `apply.verify_markdown_round_trip`. After this task
  `render_markdown_page` substitutes `vendor=vendor_path.as_posix()`, so any template must write
  `$prefix$vendor` to get a working relative URL.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_render_markdown.py`, inside `class RoundTripTests`:

```python
    def test_crlf_line_endings_normalise_to_lf(self) -> None:
        # Git with core.autocrlf=input stores LF for a CRLF working file, so a page that
        # keeps CRs is not the page that gets published. See M4-b.
        page = render.render_markdown_page(
            ENTRY, b"# Title\r\n\r\nBody\r\n", PurePosixPath("vendor/marked.min.js"),
            SITE, TEMPLATE,
        )
        self.assertNotIn(b"\r", page)
        self.assertEqual("# Title\n\nBody\n", render.extract_markdown(page.decode("utf-8")))

    def test_a_lone_carriage_return_normalises_to_lf(self) -> None:
        page = render.render_markdown_page(
            ENTRY, b"# Title\rBody\r", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        )
        self.assertEqual("# Title\nBody\n", render.extract_markdown(page.decode("utf-8")))
```

Add to `tests/test_render_html.py`, inside `class TransformTests`:

```python
    def test_crlf_line_endings_normalise_to_lf(self) -> None:
        out = render.transform_html(b"<html><head></head><body>x</body></html>\r\n", entry(), SITE)
        self.assertNotIn(b"\r", out)
        self.assertTrue(out.endswith(b"\n"))
```

Replace `test_the_vendor_path_is_relative_to_the_destination_depth` in
`tests/test_render_markdown.py` with two tests, because the shipped template and an arbitrary
template are two different claims:

```python
    def test_the_shipped_template_climbs_to_the_vendor_file(self) -> None:
        page = render.render_markdown_page(
            ENTRY, b"# x\n", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        ).decode("utf-8")
        self.assertIn('<script src="../../vendor/marked.min.js"></script>', page)

    def test_prefix_and_vendor_are_separate_placeholders(self) -> None:
        # A template using both, as the design documents and the prior art's does.
        template = string.Template("$prefix|$vendor|$block_start$markdown$block_end")
        page = render.render_markdown_page(
            ENTRY, b"# x\n", PurePosixPath("vendor/marked.min.js"), SITE, template
        ).decode("utf-8")
        self.assertTrue(page.startswith("../../|vendor/marked.min.js|"), page[:60])
```

Add to `tests/test_apply.py`, inside `class RoundTripVerificationTests`:

```python
    def test_a_crlf_source_still_verifies_against_the_lf_page(self) -> None:
        from artefact_sync import render

        entry = Entry(
            id="e", source=PurePosixPath("a.md"),
            destination=PurePosixPath("a/index.html"), title="A",
            collection="c", order=10, replacements={},
        )
        template = string.Template("<html>$block_start$markdown$block_end</html>")
        rendered = render.render_markdown_page(
            entry,
            b"# x\r\n",
            PurePosixPath("vendor/marked.min.js"),
            site_from_dict({"base_url": "https://x.example/artefacts/"}),
            template,
        )
        self.assertIsNone(a.verify_markdown_round_trip(b"# x\r\n", rendered, "a.md"))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest tests.test_render_markdown tests.test_render_html tests.test_apply -v`

Expected: `test_crlf_line_endings_normalise_to_lf` fails in both render modules (CR survives),
`test_a_lone_carriage_return_normalises_to_lf` fails, and
`test_prefix_and_vendor_are_separate_placeholders` fails with `../../|../../vendor/...`.
`test_a_crlf_source_still_verifies_against_the_lf_page` passes already, because nothing normalises
yet on either side of the comparison. `test_the_shipped_template_climbs_to_the_vendor_file` passes
for the wrong reason and will keep passing.

- [ ] **Step 3: Add `normalise_source_text` and route the three callers through it**

In `artefact_sync/render.py`, add above `escape_markdown_block`:

```python
def normalise_source_text(source_bytes: bytes, label: str) -> str:
    """Decode, normalise line endings, and guarantee a final newline.

    Line endings are normalised because git with `core.autocrlf=input` — a common
    default — stores LF for a CRLF working-tree file, so a page keeping its CRs is
    not the page that gets published, and a fresh clone never converges.
    """
    try:
        text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TransformationError(f"{label}: not valid UTF-8 ({error})") from error
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text and not text.endswith("\n"):
        text += "\n"
    return text
```

In `render_markdown_page`, replace the decode-and-newline block and the `vendor` substitution:

```python
    text = normalise_source_text(source_bytes, entry.source.as_posix())
    prefix = "../" * len(entry.destination.parent.parts)
    document = template.substitute(
        title=html.escape(entry.title),
        favicon=site.favicon,
        prefix=prefix,
        vendor=vendor_path.as_posix(),
        markdown=escape_markdown_block(text),
        block_start=BLOCK_START,
        block_end=BLOCK_END,
    )
```

In `transform_html`, replace the decode block and drop the now-dead tail:

```python
    text = normalise_source_text(source_bytes, entry.source.as_posix())
    for old, new in entry.replacements.items():
        parts = text.split(old)
        if len(parts) == 1:
            raise TransformationError(f"expected replacement not found for {entry.id}: {old}")
        text = new.join(parts)
    text = TRAILING_SPACE.sub("", text)
    text = ensure_favicon(text, site.favicon)
    return text.encode("utf-8")
```

Moving the final newline ahead of the replacements is safe: `TRAILING_SPACE` matches at end of
string as well as before a line end, and `ensure_favicon` only touches the head of the document.

In `artefact_sync/apply.py`, extend the existing module-level import and drop the manual decode:

```python
from .render import extract_markdown, normalise_source_text
```

```python
def verify_markdown_round_trip(source_bytes: bytes, rendered: bytes, label: str) -> None:
    try:
        expected = normalise_source_text(source_bytes, label)
        document = rendered.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(f"{label}: markdown round trip is not UTF-8 ({error})") from error
    found = extract_markdown(document)
```

`TransformationError` from `normalise_source_text` is not a `ValidationError`, so let it propagate: a
source that stopped being UTF-8 between plan and apply is a transformation failure, and its message
already names the file.

In `artefact_sync/assets/page-template.html`, change the vendor line:

```html
    <script src="$prefix$vendor"></script>
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_render_markdown tests.test_render_html tests.test_apply -v`
Expected: PASS, all of them.

Then the whole suite on both interpreters:

```bash
python3 -m unittest discover -s tests -t . 2>&1 | tail -3
/usr/bin/python3 -m unittest discover -s tests -t . 2>&1 | tail -3
```

Expected: OK on both, 232 tests.

- [ ] **Step 5: Commit**

```bash
git add artefact_sync/render.py artefact_sync/apply.py \
        artefact_sync/assets/page-template.html \
        tests/test_render_markdown.py tests/test_render_html.py tests/test_apply.py
git commit -m "fix(render): normalise line endings, and let \$prefix and \$vendor compose"
```

---

### Task 2: the embedded block matches what the prior art published

**Files:**
- Modify: `artefact_sync/render.py:13` (`BLOCK_START`)
- Modify: `artefact_sync/assets/page-template.html` (the reader script)
- Test: `tests/test_render_markdown.py`, `tests/test_apply.py`

**Interfaces:**
- Consumes: `render.BLOCK_START`, `render.BLOCK_END`, `render.extract_markdown`,
  `render.render_markdown_page`, `apply.verify_markdown_round_trip`.
- Produces: `render.BLOCK_START == '<script type="text/markdown" id="markdown-source">\n'`.
  `extract_markdown` needs no change: it slices from `find(BLOCK_START) + len(BLOCK_START)`, which
  now lands after the newline. Any page template must read `markdown-source` and strip one leading
  newline from `textContent`.

- [ ] **Step 1: Write the failing tests**

Replace `test_the_renderer_reads_the_embedded_source_block_id` and
`test_the_browser_does_not_strip_a_leading_source_newline` in `tests/test_render_markdown.py`
::`TemplateTests` with:

```python
    def test_the_page_and_its_reader_agree_on_the_block_id(self) -> None:
        page = render.render_markdown_page(
            ENTRY, b"# x\n", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        ).decode("utf-8")
        self.assertIn('id="markdown-source"', page)
        self.assertIn("getElementById('markdown-source')", page)
        self.assertNotIn("artefact-source", page)

    def test_the_source_starts_on_the_line_after_the_opening_tag(self) -> None:
        # The prior art published every page this way, so changing it would rewrite
        # every Markdown page an adopter has. See M4-c.
        page = render.render_markdown_page(
            ENTRY, b"# x\n", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        ).decode("utf-8")
        self.assertIn('<script type="text/markdown" id="markdown-source">\n# x\n</script>', page)

    def test_the_browser_strips_the_leading_source_newline(self) -> None:
        # textContent begins at that newline; extract_markdown's slice does not.
        raw = Path("artefact_sync/assets/page-template.html").read_text(encoding="utf-8")
        self.assertIn(r".replace(/^\n/, '')", raw)
```

In `tests/test_apply.py`, update the hardcoded literal in
`test_raises_when_the_page_carries_different_markdown` so the test fails on mismatched Markdown
rather than on an unreadable block:

```python
    def test_raises_when_the_page_carries_different_markdown(self) -> None:
        rendered = (b'<script type="text/markdown" id="markdown-source">\n'
                    b"# DIFFERENT\n</script>")
        with self.assertRaises(ValidationError):
            a.verify_markdown_round_trip(b"# x\n", rendered, "a.md")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest tests.test_render_markdown.TemplateTests -v`
Expected: `test_the_page_and_its_reader_agree_on_the_block_id` fails on `id="markdown-source"`,
`test_the_source_starts_on_the_line_after_the_opening_tag` fails, and
`test_the_browser_strips_the_leading_source_newline` fails.

- [ ] **Step 3: Change the constant and the shipped template**

In `artefact_sync/render.py`:

```python
BLOCK_START = '<script type="text/markdown" id="markdown-source">\n'
```

In `artefact_sync/assets/page-template.html`, replace the first two lines of the reader script:

```javascript
        (function () {
            // textContent starts at the newline that follows the opening tag, which
            // the Python-side extract_markdown slice does not include. Drop it so
            // both sides see the same bytes.
            var raw = document.getElementById('markdown-source').textContent.replace(/^\n/, '');
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_render_markdown tests.test_apply -v`
Expected: PASS. `RoundTripTests::test_a_leading_blank_line_survives_embedding_and_extraction` is the
one to watch: a source of `"\n# Title\n"` now embeds as `>\n\n# Title\n`, and extraction must still
return `"\n# Title\n"`.

Then both interpreters:

```bash
python3 -m unittest discover -s tests -t . 2>&1 | tail -3
/usr/bin/python3 -m unittest discover -s tests -t . 2>&1 | tail -3
```

Expected: OK on both, 233 tests.

- [ ] **Step 5: Commit**

```bash
git add artefact_sync/render.py artefact_sync/assets/page-template.html \
        tests/test_render_markdown.py tests/test_apply.py
git commit -m "fix(render): publish the markdown-source block the prior art published"
```

---

### Task 3: the catalogue emits the markup a host page can style

**Files:**
- Modify: `artefact_sync/catalogue.py` (replace `_invert`/`entry_sort_key` with `section_slug`;
  rewrite `render_catalogue`)
- Modify: `artefact_sync/assets/catalogue-template.html` (CSS class names)
- Test: `tests/test_catalogue.py`

**Interfaces:**
- Consumes: `manifest.Manifest`, `manifest.Collection`, `manifest.Entry`, `config.Site`,
  `catalogue.replace_generated_catalogue`, `catalogue.render_standalone_catalogue`,
  `catalogue.public_href`.
- Produces: `catalogue.section_slug(value: str) -> str`; `catalogue.render_catalogue(manifest, site)`
  keeps its signature and returns the prior art's markup. `catalogue.entry_sort_key` and
  `catalogue._invert` are **removed**; nothing outside `tests/test_catalogue.py` calls them.
  `config.py` is not touched — see M4-j.

- [ ] **Step 1: Write the failing tests**

In `tests/test_catalogue.py`, replace the `build` helper and add a `collection` helper so a test can
construct more than one collection:

```python
def collection(**overrides) -> Collection:
    body = dict(id="c", title="C", description=None, section="S", section_order=10, order=10)
    body.update(overrides)
    return Collection(**body)


def build(entries, collections=None) -> Manifest:
    return Manifest(
        version=1, site=SITE, protected_files=(), ignored_sources=(),
        collections=tuple(collections or (collection(),)),
        entries=tuple(entries),
    )
```

Then replace `class SortTests` entirely with:

```python
class MarkupTests(unittest.TestCase):
    def test_a_card_carries_the_classes_a_host_page_styles(self) -> None:
        fragment = catalogue.render_catalogue(build([entry(date="2026-06-01")]), SITE)
        self.assertIn('<section aria-labelledby="s-heading">', fragment)
        self.assertIn('<h2 id="s-heading">S</h2>', fragment)
        self.assertIn('<div class="card-grid">', fragment)
        self.assertIn('<article class="card">', fragment)
        self.assertIn('<li><a href="a/">A</a></li>', fragment)

    def test_a_dated_card_says_when_it_was_updated(self) -> None:
        fragment = catalogue.render_catalogue(build([entry(date="2026-06-01")]), SITE)
        self.assertIn(
            '<p class="card-updated">Updated <time datetime="2026-06-01">2026-06-01</time></p>',
            fragment,
        )

    def test_an_undated_card_says_nothing_about_dates(self) -> None:
        self.assertNotIn("card-updated", catalogue.render_catalogue(build([entry()]), SITE))

    def test_a_section_heading_id_is_slugged(self) -> None:
        fragment = catalogue.render_catalogue(
            build([entry()], [collection(section="Image collections")]), SITE
        )
        self.assertIn('<h2 id="image-collections-heading">Image collections</h2>', fragment)

    def test_titles_are_escaped(self) -> None:
        fragment = catalogue.render_catalogue(build([entry(title="a <b> & c")]), SITE)
        self.assertIn("a &lt;b&gt; &amp; c", fragment)
        self.assertNotIn("<b>", fragment)


class CardOrderTests(unittest.TestCase):
    def test_the_newest_card_comes_first(self) -> None:
        manifest = build(
            [entry(id="o", destination=PurePosixPath("o/index.html"), collection="old",
                   date="2026-01-01"),
             entry(id="n", destination=PurePosixPath("n/index.html"), collection="new",
                   date="2026-06-01")],
            [collection(id="old", title="Old", order=10),
             collection(id="new", title="New", order=20)],
        )
        fragment = catalogue.render_catalogue(manifest, SITE)
        self.assertLess(fragment.index("<h3>New</h3>"), fragment.index("<h3>Old</h3>"))

    def test_an_undated_card_falls_to_the_bottom(self) -> None:
        manifest = build(
            [entry(id="u", destination=PurePosixPath("u/index.html"), collection="undated"),
             entry(id="d", destination=PurePosixPath("d/index.html"), collection="dated",
                   date="2026-01-01")],
            [collection(id="undated", title="Undated", order=10),
             collection(id="dated", title="Dated", order=20)],
        )
        fragment = catalogue.render_catalogue(manifest, SITE)
        self.assertLess(fragment.index("<h3>Dated</h3>"), fragment.index("<h3>Undated</h3>"))

    def test_cards_sharing_a_date_keep_their_declared_order(self) -> None:
        manifest = build(
            [entry(id="b", destination=PurePosixPath("b/index.html"), collection="second",
                   date="2026-01-01"),
             entry(id="a", destination=PurePosixPath("a2/index.html"), collection="first",
                   date="2026-01-01")],
            [collection(id="first", title="First", order=10),
             collection(id="second", title="Second", order=20)],
        )
        fragment = catalogue.render_catalogue(manifest, SITE)
        self.assertLess(fragment.index("<h3>First</h3>"), fragment.index("<h3>Second</h3>"))

    def test_a_cards_date_is_its_newest_entry(self) -> None:
        manifest = build([
            entry(id="old", destination=PurePosixPath("o/index.html"), date="2026-01-01"),
            entry(id="new", destination=PurePosixPath("n/index.html"), date="2026-06-01"),
        ])
        self.assertIn('datetime="2026-06-01"', catalogue.render_catalogue(manifest, SITE))


class EntryOrderTests(unittest.TestCase):
    def test_entries_inside_a_card_keep_their_declared_order_whatever_their_dates(self) -> None:
        # A card's date answers "is this collection fresh". Position inside a card is
        # editorial, and the prior art sorts on order alone. See M4-d.
        manifest = build([
            entry(id="first", title="First", destination=PurePosixPath("f/index.html"),
                  order=10, date="2026-01-01"),
            entry(id="second", title="Second", destination=PurePosixPath("s/index.html"),
                  order=20, date="2026-06-01"),
        ])
        fragment = catalogue.render_catalogue(manifest, SITE)
        self.assertLess(fragment.index(">First<"), fragment.index(">Second<"))
```

The module already imports `Collection`; add no imports.

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest tests.test_catalogue -v`
Expected: every new `MarkupTests`, `CardOrderTests` and `EntryOrderTests` case fails.
`InjectionTests` and `StandaloneTests` keep passing.

- [ ] **Step 3: Rewrite `render_catalogue`**

In `artefact_sync/catalogue.py`, add `import re` to the imports, delete `_invert` and
`entry_sort_key`, and put this in their place:

```python
_SLUG = re.compile(r"[^a-z0-9]+")


def section_slug(value: str) -> str:
    return _SLUG.sub("-", value.lower()).strip("-")
```

Then replace `render_catalogue` entirely:

```python
def render_catalogue(manifest: Manifest, site: Site) -> str:
    """The fragment a host page styles. Markup and ordering follow the prior art.

    Hrefs stay relative so the same generated tree works at any site.base_url. Cards
    lead with their newest entry's date because that answers "is this collection
    fresh"; entries inside a card keep their declared order, which is editorial.
    """
    entries_by_collection: dict[str, list[Entry]] = {}
    for entry in manifest.entries:
        entries_by_collection.setdefault(entry.collection, []).append(entry)

    sections: dict[tuple[int, str], list] = {}
    for collection in manifest.collections:
        if entries_by_collection.get(collection.id):
            sections.setdefault(
                (collection.section_order, collection.section), []
            ).append(collection)

    latest = {
        collection_id: max((entry.date for entry in entries if entry.date), default="")
        for collection_id, entries in entries_by_collection.items()
    }

    lines: list[str] = []
    for (_, section_title), collections in sorted(sections.items()):
        heading_id = f"{section_slug(section_title)}-heading"
        lines.extend(
            [
                f'        <section aria-labelledby="{heading_id}">',
                f'            <h2 id="{heading_id}">{html.escape(section_title)}</h2>',
                '            <div class="card-grid">',
            ]
        )
        # Newest card first, with `order` as the tie-break: Python's sort is stable and
        # reverse=True does not reverse equal elements. An undated card sorts as "" and
        # lands last.
        cards = sorted(collections, key=lambda item: item.order)
        cards.sort(key=lambda item: latest[item.id], reverse=True)
        for collection in cards:
            lines.extend(
                [
                    '                <article class="card">',
                    f"                    <h3>{html.escape(collection.title)}</h3>",
                ]
            )
            if collection.description is not None:
                lines.append(f"                    <p>{html.escape(collection.description)}</p>")
            stamp = latest[collection.id]
            if stamp:
                lines.append(
                    '                    <p class="card-updated">Updated '
                    f'<time datetime="{stamp}">{stamp}</time></p>'
                )
            lines.append("                    <ul>")
            for entry in sorted(entries_by_collection[collection.id], key=lambda e: e.order):
                href = html.escape(public_href(entry), quote=True)
                lines.append(
                    f'                        <li><a href="{href}">'
                    f"{html.escape(entry.title)}</a></li>"
                )
            lines.extend(["                    </ul>", "                </article>"])
        lines.extend(["            </div>", "        </section>"])
    return "\n".join(lines)
```

- [ ] **Step 4: Restyle the bundled standalone catalogue**

In `artefact_sync/assets/catalogue-template.html`, replace the two class rules with three that match
the new markup:

```css
        .card-grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); }
        .card { padding: 1rem; border: 1px solid #ddd; border-radius: 0.5rem; }
        .card-updated { color: #666; font-size: 0.875rem; }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_catalogue -v`
Expected: PASS.

Then both interpreters:

```bash
python3 -m unittest discover -s tests -t . 2>&1 | tail -3
/usr/bin/python3 -m unittest discover -s tests -t . 2>&1 | tail -3
```

Expected: OK on both, 240 tests. `tests/test_m1_end_to_end.py` and `tests/test_m3_end_to_end.py`
assert on hrefs in the catalogue, which the new markup still satisfies. If either fails on markup
rather than on an href, fix the assertion, not the markup.

- [ ] **Step 6: Commit**

```bash
git add artefact_sync/catalogue.py artefact_sync/assets/catalogue-template.html \
        tests/test_catalogue.py
git commit -m "feat(catalogue): emit styleable markup and order cards by date"
```

---

### Task 4: `head_manifest` survives a HEAD that predates the `site` block

**Files:**
- Modify: `artefact_sync/manifest.py:358-367` (`head_manifest`)
- Test: `tests/test_manifest_invariants.py`

**Interfaces:**
- Consumes: `manifest.head_manifest`, `manifest.check_published_invariants`,
  `manifest.manifest_from_dict`, `tests.helpers.make_repo`.
- Produces: no signature change. `head_manifest` returns `None` for an unparseable HEAD manifest
  instead of raising, and parses one that lacks `site` by injecting a placeholder before validating.
  `check_published_invariants` therefore still sees real `id`/`destination`/`title` values from a
  manifest written before the `site` block existed.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_manifest_invariants.py`. That module binds the package as `m`, and already
imports `tempfile`, `Path` and `make_repo`; add `import json` at the top and nothing else.

```python
class AdoptionTests(unittest.TestCase):
    def test_a_head_manifest_without_a_site_block_still_freezes_destinations(self) -> None:
        # Every repository adopting the skill has one. See M4-f.
        with tempfile.TemporaryDirectory() as tmp:
            body = json.dumps({
                "version": 1,
                "protected_files": [],
                "ignored_sources": [],
                "collections": [{"id": "c", "title": "C", "section": "S",
                                 "section_order": 10, "order": 10}],
                "entries": [{"id": "e", "source": "a.md", "destination": "a/index.html",
                             "title": "A", "collection": "c", "order": 10,
                             "replacements": {}}],
            }, indent=2) + "\n"
            repo = make_repo(Path(tmp), {"artefacts/manifest.json": body.encode("utf-8")})
            head = m.head_manifest(repo)
            self.assertIsNotNone(head)
            self.assertEqual(
                ("a/index.html",),
                tuple(e.destination.as_posix() for e in head.entries),
            )

    def test_an_unreadable_head_manifest_leaves_the_invariants_unchecked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp), {"artefacts/manifest.json": b"not json at all\n"})
            self.assertIsNone(m.head_manifest(repo))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest tests.test_manifest_invariants -v`
Expected: `test_a_head_manifest_without_a_site_block_still_freezes_destinations` fails with
`ValidationError: missing manifest field: site`, and
`test_an_unreadable_head_manifest_leaves_the_invariants_unchecked` fails with
`ValidationError: cannot read manifest`.

- [ ] **Step 3: Make the HEAD read lenient**

In `artefact_sync/manifest.py`, replace `head_manifest`:

```python
def head_manifest(repo_root: Path) -> Manifest | None:
    """The manifest as of HEAD, or None when it was never committed or cannot be read.

    Read leniently on purpose. This value only ever feeds `check_published_invariants`,
    which reads `id`, `destination` and `title`. A repository adopting the skill has a
    committed manifest with no `site` block, so failing the whole run on a field the
    check never touches would make adoption impossible — while returning None outright
    would drop the URL-freeze guard on exactly the run where published destinations are
    at stake. Injecting a placeholder keeps the guard.
    """
    result = subprocess.run(
        ["git", "show", f"HEAD:artefacts/{MANIFEST_NAME}"],
        cwd=str(repo_root),
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict):
        payload.setdefault("site", {"base_url": "https://head.invalid/"})
    try:
        return manifest_from_dict(payload)
    except ValidationError:
        return None
```

`json`, `ValidationError` and `manifest_from_dict` are all already in scope in that module.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_manifest_invariants -v`
Expected: PASS.

Then both interpreters:

```bash
python3 -m unittest discover -s tests -t . 2>&1 | tail -3
/usr/bin/python3 -m unittest discover -s tests -t . 2>&1 | tail -3
```

Expected: OK on both, 242 tests.

- [ ] **Step 5: Commit**

```bash
git add artefact_sync/manifest.py tests/test_manifest_invariants.py
git commit -m "fix(manifest): adopt a repo whose committed manifest predates the site block"
```

---

### Task 5: adoption — the offline proof, the ignore-rule hazard, and `SKILL.md`

**Files:**
- Create: `tests/test_m4_adoption.py`
- Modify: `tests/test_scan.py`
- Modify: `SKILL.md`

**Interfaces:**
- Consumes: everything Tasks 1-4 produced, plus `cli.main`, `cli.EXIT_OK`, `scan.is_ignored`,
  `tests.helpers.make_repo`, `tests.helpers.make_source_tree`. Adds no new interface.

`test_m4_adoption.py` is the offline stand-in for Tasks 6 and 7. Those run the real comparison once;
this runs the same shape on every commit forever, and it is where the CRLF path stays covered,
because the real corpus has no CRLF source.

- [ ] **Step 1: Write the adoption test**

Create `tests/test_m4_adoption.py`:

```python
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from artefact_sync import cli
from tests.helpers import make_repo, make_source_tree

# A source with CRLF endings and no final newline: both normalisations at once.
# The M4 probe corpus has neither, so this test is where that path stays covered.
CRLF_NOTE = b"# Cost model\r\n\r\nBuild versus buy."
PAGE = b"<html><head><title>P</title></head><body>Hi</body></html>\n"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin"}


def _commit(repo: Path, message: str) -> None:
    for args in (["add", "-A"], ["commit", "-q", "-m", message]):
        subprocess.run(["git", *args], cwd=repo, env=GIT_ENV, check=True)


def _seed_published_tree(repo: Path, source: Path) -> Path:
    """Publish once, commit, and hand back the pointer path.

    Committing matters: git normalises CRLF on commit under core.autocrlf=input, so
    the committed bytes are what a second machine — or a fresh clone — would see.
    """
    pointer = repo.parent / "pointer.json"
    cli.main(["init", "--pointer", str(pointer), "--repo", str(repo), "--source", str(source)])
    cli.main(["plan", "--pointer", str(pointer)])
    cli.main(["sync", "--pointer", str(pointer), "--yes"])
    _commit(repo, "publish")
    return pointer


class AdoptionTests(unittest.TestCase):
    def test_a_published_tree_is_not_rewritten_on_re_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"note.md": CRLF_NOTE, "page.html": PAGE})
            pointer = _seed_published_tree(repo, source)

            self.assertEqual(cli.EXIT_OK, cli.main(["plan", "--pointer", str(pointer)]))
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            # git status can report a line-ending-only change; the commit diff cannot.
            changed = subprocess.run(
                ["git", "diff", "--name-only", "HEAD", "--", "artefacts"],
                cwd=repo, capture_output=True, text=True,
            ).stdout
            self.assertEqual("", changed)

    def test_the_published_page_carries_no_carriage_returns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"note.md": CRLF_NOTE})
            _seed_published_tree(repo, source)
            page = (repo / "artefacts" / "note" / "index.html").read_bytes()
            self.assertNotIn(b"\r", page)
            self.assertIn(b"Build versus buy.\n", page)

    def test_a_manifest_committed_without_a_site_block_is_adoptable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"note.md": b"# n\n"})
            pointer = _seed_published_tree(repo, source)
            # Rewrite HEAD's manifest to the pre-site shape a real adopter has.
            path = repo / "artefacts" / "manifest.json"
            body = json.loads(path.read_text(encoding="utf-8"))
            body.pop("site")
            path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
            _commit(repo, "pre-site manifest")
            # Put the site block back in the working copy only, as adoption does.
            body["site"] = {"base_url": "https://x.example/artefacts/",
                            "catalogue": {"mode": "standalone"}}
            path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(cli.EXIT_OK, cli.main(["plan", "--pointer", str(pointer)]))
```

- [ ] **Step 2: Pin the ignore-rule hazard**

Add to `tests/test_scan.py`, beside the existing `is_ignored` cases:

```python
    def test_a_bare_directory_rule_matches_that_directory_at_any_depth(self) -> None:
        # The prior art matched a "dir/" rule only at the root, which is why manifests
        # written by it carry full prefixes like "fde/prompts/". Carrying such a
        # manifest over and shortening a rule silently widens it. See M4-i.
        self.assertTrue(scan.is_ignored(PurePosixPath("a/b/prompts/x.md"), ("prompts/",)))
        self.assertTrue(scan.is_ignored(PurePosixPath("prompts/x.md"), ("prompts/",)))
        self.assertFalse(scan.is_ignored(PurePosixPath("a/prompts.md"), ("prompts/",)))
```

- [ ] **Step 3: Run both**

Run: `python3 -m unittest tests.test_m4_adoption tests.test_scan -v`, and again under
`/usr/bin/python3`.
Expected: all PASS. The `test_scan.py` case passes immediately — it pins behaviour `manifest.is_ignored`
already has, which the probe exposed and nothing covered. If
`test_a_published_tree_is_not_rewritten_on_re_adoption` reports a changed file, one of Tasks 1-4 is
incomplete; do not weaken the assertion.

- [ ] **Step 4: Update `SKILL.md`**

Add a new section immediately before `## Safety`:

```markdown
## Adopting an existing artefacts tree

A repository that already publishes an `artefacts/` tree keeps every URL it has published. Work in
this order, and never delete a published file to resolve a mismatch.

1. Add a `site` block to `artefacts/manifest.json`: `base_url`, `favicon`, and `catalogue` in
   `inject` mode naming the page that carries the `ARTEFACTS:START` / `ARTEFACTS:END` markers.
2. Copy the page template the tree was published with to `artefacts/page-template.html`. If it came
   from a `str.format` template, convert `{name}` to `$name` and collapse `{{` and `}}` to single
   braces. Placeholders are `$title`, `$favicon`, `$prefix`, `$vendor`, `$markdown`, `$block_start`
   and `$block_end`; the vendor script tag is `src="$prefix$vendor"`.
3. Keep the `ignored_sources` rules exactly as they are, including any long prefixes. A rule ending
   in `/` matches that directory name at any depth, so shortening `docs/prompts/` to `prompts/`
   silently ignores every other `prompts` directory, and those files then read as deletions.
   Dotfile directories are the usual gap in an older manifest: `.*` covers them.
4. Run `plan`. Every entry that reports as changed is a rendering difference to explain before you
   sync, not after. `manifest.json` always changes on the first run, because absent `date` values
   are stamped from source modification time.
5. Run `sync`, then `git diff --name-only HEAD -- artefacts`. Anything beyond
   `artefacts/manifest.json` means the tool renders that file differently from whatever built it.
   Stop and read the diff. Use `git diff`, not `git status`: with `core.autocrlf` set, status
   reports a working-tree line-ending change that commits as nothing.
6. Run `plan` again. It must report no change groups. That is the proof the adoption converged.
```

- [ ] **Step 5: Run the whole suite on both interpreters**

```bash
python3 -m unittest discover -s tests -t . 2>&1 | tail -3
/usr/bin/python3 -m unittest discover -s tests -t . 2>&1 | tail -3
git -C /Users/keli/dev/github-kevinlin/kevinlin.github.io status --short
```

Expected: OK on both, 246 tests. The third command prints nothing.

- [ ] **Step 6: Commit**

```bash
git add tests/test_m4_adoption.py tests/test_scan.py SKILL.md
git commit -m "test: prove an existing published tree survives adoption unrewritten"
```

---

### Task 6: the fixture — a probe tree the prior art published

**Files:**
- Creates outside the repository: `~/dev/github-kevinlin/artefacts-test`
- Reads only: `~/Downloads/Claude-Artefacts`, and `scripts/artefacts.py` from the profile repository

**Interfaces:**
- Produces the probe repository Task 7 consumes. No code in this repository changes.

Nothing here runs the skill. The deliverable is a published tree with a known provenance: the prior
art wrote every byte of it.

- [ ] **Step 1: Inventory the source folder, and re-check the live corpus**

The corpus is real and mutable, so record what it was. This is the reproducibility substitute for a
generated fixture, and it belongs in the acceptance record.

```bash
python3 - <<'PY'
import hashlib
from pathlib import Path
root = Path.home() / "Downloads" / "Claude-Artefacts"
for path in sorted(root.rglob("*")):
    if not path.is_file() or path.name == ".DS_Store":
        continue
    data = path.read_bytes()
    print(f"{len(data):>10,}  {hashlib.sha256(data).hexdigest()[:16]}  "
          f"{path.relative_to(root).as_posix()}")
PY
```

Expected, from when this plan was written:

```
    31,911  914adf545f413e5d  coding-agent-adoption.html
     1,792  4b2db67d0104453f  mingpt-vs-toy-transformer/analysis.md
 2,130,205  b27c7bc35470172b  mingpt-vs-toy-transformer/infographic.png
     4,414  a2df7bb56c8417f1  mingpt-vs-toy-transformer/prompts/infographic.md
     3,663  f2c5bceae501232f  mingpt-vs-toy-transformer/source-mingpt-vs-toy-transformer.md
     2,718  29d2fee296373266  mingpt-vs-toy-transformer/structured-content.md
    38,189  1e159c345d2ad99a  star-wars-timeline.html
```

A different list is not a failure — the folder is real and may have moved on. Record what you got,
and expect the entry count in Task 7 to move with it.

Then confirm the live corpus is still what the coverage table in "Why a probe" was written against.
This reads the profile repository and writes nothing:

```bash
SITE=/Users/keli/dev/github-kevinlin/kevinlin.github.io
git -C "$SITE" status --short          # must print nothing
python3 - <<'PY'
import json
from pathlib import Path
from collections import Counter
from artefact_sync import scan
site = Path("/Users/keli/dev/github-kevinlin/kevinlin.github.io")
raw = json.loads((site / "artefacts" / "manifest.json").read_text())
print("live entries", len(raw["entries"]), "collections", len(raw["collections"]),
      "protected", len(raw["protected_files"]))
print("live entry suffixes", Counter(Path(e["source"]).suffix for e in raw["entries"]))
inventory = scan.scan_source(Path.home() / "Downloads" / "Artefacts", site)
kept, _ = scan.apply_source_ignores(inventory, tuple(raw["ignored_sources"]))
listed = {e["source"] for e in raw["entries"]}
print("live approved", len(inventory.approved), "after ignores", len(kept.approved),
      "unlisted", len([p for p in kept.approved if p.as_posix() not in listed]))
PY
git -C "$SITE" status --short          # must still print nothing
```

Reference values against live HEAD `280b17e`: 56 entries, 31 collections, 36 protected; 26 `.png`,
14 `.html`, 9 `.md`, 5 `.jpeg`, 2 `.jpg`; 128 approved, 66 after ignores, 10 unlisted.

- [ ] **Step 2: Create the probe repository shell**

The prior art cannot run in a repository whose catalogue shell is missing, so the shell comes first.
It is also the host page whose CSS Task 3's markup has to fit, which is the point.

```bash
PROBE=~/dev/github-kevinlin/artefacts-test
mkdir -p "$PROBE/artefacts/vendor" "$PROBE/artefacts/showcase"
cp /Users/keli/dev/ai-practitioner/artefact-sync/artefact_sync/assets/marked.min.js \
   "$PROBE/artefacts/vendor/marked.min.js"
```

Write `$PROBE/artefacts/showcase/index.html` — a hand-written page the tool must never touch, which
is how the gate covers `protected_files`:

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Showcase</title></head>
<body><p>Stand-in for a hand-written page the tool must never touch.</p></body>
</html>
```

Write `$PROBE/artefacts/index.html`, the host page:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Artefacts</title>
    <style>
        body { margin: 0 auto; max-width: 72rem; padding: 2rem 1rem;
               font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
        .card-grid { display: grid; gap: 1rem;
                     grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); }
        .card { padding: 1rem; border: 1px solid #ddd; border-radius: 0.5rem; }
        .card-updated { color: #666; font-size: 0.875rem; }
    </style>
</head>
<body>
    <main>
        <h1>Artefacts</h1>
<!-- ARTEFACTS:START -->
<!-- ARTEFACTS:END -->
    </main>
</body>
</html>
```

Write `$PROBE/artefacts/manifest.json` in the prior art's schema — no `site` block, because that is
the shape an adopter actually has, and Task 4 exists for it. The ignore rule carries its full prefix
so both implementations match it identically; see M4-i:

```json
{
  "version": 1,
  "protected_files": [
    "showcase/index.html",
    "vendor/marked.min.js"
  ],
  "ignored_sources": [
    "mingpt-vs-toy-transformer/prompts/"
  ],
  "collections": [],
  "entries": []
}
```

Then:

```bash
git -C "$PROBE" init -q -b main
git -C "$PROBE" add -A
git -C "$PROBE" commit -q -m "probe shell"
git -C "$PROBE" ls-files
```

Expected: the four files above.

- [ ] **Step 3: Publish the probe tree with the prior art**

Copy the script out rather than running it in place, so the profile repository is never even a
working directory, and use `-B` so no bytecode is written anywhere near it.

```bash
SITE=/Users/keli/dev/github-kevinlin/kevinlin.github.io
cp "$SITE/scripts/artefacts.py" /tmp/artefacts_prior_art.py
git -C "$SITE" status --short          # must print nothing
```

The first run proposes and stops; the second applies. `apply` prompts, so drive it through `main`'s
injectable `input_fn`:

```bash
cd /tmp
python3 -B - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "/tmp")
import artefacts_prior_art as artefacts
probe = str(Path.home() / "dev/github-kevinlin/artefacts-test")
source = str(Path.home() / "Downloads/Claude-Artefacts")
for round_number in (1, 2):
    code = artefacts.main(["apply", "--repo", probe, "--source", source],
                          input_fn=lambda prompt: "yes")
    print(f"round {round_number}: exit {code}")
PY
```

Expected: round 1 exits 3 with `Wrote artefacts/manifest.json. Review the derived titles and
descriptions, then run the command again to publish.` and 6 proposals; round 2 exits 0, applies, and
reports `Ignored sources (1) - mingpt-vs-toy-transformer/prompts/ (1 file)`.

Then read what it produced:

```bash
PROBE=~/dev/github-kevinlin/artefacts-test
find "$PROBE/artefacts" -type f | sed "s|$PROBE/artefacts/||" | sort
python3 -c "
import json, pathlib
m = json.loads((pathlib.Path.home() / 'dev/github-kevinlin/artefacts-test/artefacts/manifest.json').read_text())
print('entries', len(m['entries']), 'collections', len(m['collections']))
for c in m['collections']: print(' ', c['id'], repr(c['section']))
"
grep -o '<h2 id="[^"]*"' "$PROBE/artefacts/index.html"
```

Expected: 10 files — 6 entry destinations, `index.html`, `manifest.json`, `showcase/index.html`,
`vendor/marked.min.js`; 6 entries in 2 collections (`coding-agent-adoption` and
`mingpt-vs-toy-transformer`), both in `Presentations and analysis`; and one section heading,
`presentations-and-analysis-heading`.

One section means the prior art emits no showcase link, which is why M4-j leaves `section_links`
unbuilt. Note the collection named `coding-agent-adoption` holding both root-level pages: that is the
prior art's root-collection naming, the defect M3-b fixed in the skill's proposer. The skill reads
this manifest rather than re-deriving it, so it inherits the name and nothing diverges.

- [ ] **Step 4: Commit the baseline and check the profile repository**

```bash
PROBE=~/dev/github-kevinlin/artefacts-test
git -C "$PROBE" add -A
git -C "$PROBE" commit -m "publish via the prior art"
git -C "$PROBE" log --oneline
git -C /Users/keli/dev/github-kevinlin/kevinlin.github.io status --short
```

Expected: two commits, and the last command prints nothing.

---

### Task 7: the gate — the skill reproduces the prior art, byte for byte

**Files:**
- Create: `docs/specs/m4-acceptance.md` (rows 1 onwards)
- Modify: `docs/specs/design_artefact-sync.md` (corrections M4-a to M4-k)
- Modifies outside the repository: the probe repository's `artefacts/`

**Interfaces:**
- Consumes: the whole CLI, and Task 6's committed probe tree. Produces no code.

Numbers below are what a run produced while this plan was written, with all four fixes applied to a
scratch copy of the package. A mismatch is information: record it, do not adjust an assertion to
hide it.

- [ ] **Step 1: Write the adoption prep**

Two things the prior art's tree does not carry: a `site` block and a `page-template.html`. Leave both
uncommitted, so this run also proves Task 4 against a HEAD manifest that has no `site`. No dotfile
rule is added — this corpus has no dotfile directory, and adding a rule that matches nothing would
only pad the diff.

```bash
cd /Users/keli/dev/ai-practitioner/artefact-sync
python3 -B - <<'PY'
import json, re, sys
from pathlib import Path
sys.path.insert(0, "/tmp")
import artefacts_prior_art as artefacts

probe = Path.home() / "dev/github-kevinlin/artefacts-test"

# The page template, converted for string.Template. Sentinels first, so a literal
# {{word}} could never be mistaken for a placeholder; the constant has no "$", so
# nothing needs doubling on the way out.
text = artefacts.MARKDOWN_PAGE_TEMPLATE
assert "$" not in text and "\x00" not in text and "\x01" not in text
text = text.replace("{{", "\x00").replace("}}", "\x01")
text = re.sub(r"\{(\w+)\}", r"$\1", text)
text = text.replace("\x00", "{").replace("\x01", "}")
(probe / "artefacts/page-template.html").write_text(text, encoding="utf-8")

path = probe / "artefacts/manifest.json"
old = json.loads(path.read_text(encoding="utf-8"))
new = {
    "version": old["version"],
    "site": {
        "base_url": "https://kevinlin.github.io/artefacts-test/artefacts/",
        "favicon": artefacts.FAVICON_LINK,
        "catalogue": {"mode": "inject", "page": "index.html"},
    },
    "protected_files": old["protected_files"],
    "ignored_sources": old["ignored_sources"],
    "collections": old["collections"],
    "entries": old["entries"],
}
path.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")

pointer = Path.home() / ".config/artefact-sync/config.json"
pointer.parent.mkdir(parents=True, exist_ok=True)
pointer.write_text(json.dumps({
    "repo": str(probe),
    "source": str(Path.home() / "Downloads/Claude-Artefacts"),
    "push": "direct",
}, indent=2) + "\n", encoding="utf-8")
print("adoption prep written, uncommitted")
PY
```

- [ ] **Step 2: Run the gate**

```bash
python3 -m artefact_sync plan | grep -E '^[A-Z][A-Z ]*\([0-9]+\)|^  '
```

Expected:

```
CHANGED (1)
  https://kevinlin.github.io/artefacts-test/artefacts/manifest.json
EXCLUDED (1)
  mingpt-vs-toy-transformer/prompts/ 1 file, matched an ignored source rule
WARNINGS (8)
  external  coding-agent-adoption.html:592    loads https://www.anthropic.com/... at runtime
  ... six more from coding-agent-adoption.html, lines 593-598
  external  star-wars-timeline.html:462    loads https://mp.weixin.qq.com/... at runtime
```

No `NEW PUBLIC URLS`, no `WILL START 404-ING`, no `BLOCKED`, exit 0. `manifest.json` changes because
absent `date` values get stamped; nothing else changes at all, which is already most of the gate.

All 8 warnings are off-site references in the two hand-built HTML pages. Read them: they are
citation links in the page body, not runtime dependencies, and `plan` warns on any external
reference by design because it cannot tell the difference.

- [ ] **Step 3: Prove no published byte moved**

```bash
PROBE=~/dev/github-kevinlin/artefacts-test
python3 -m artefact_sync sync --yes > /dev/null
git -C "$PROBE" diff --name-only HEAD -- artefacts
git -C "$PROBE" ls-files --others --exclude-standard artefacts
git -C "$PROBE" add -A artefacts && git -C "$PROBE" diff --cached --name-status
git -C "$PROBE" reset -q
```

Expected:

```
artefacts/manifest.json
artefacts/page-template.html
M	artefacts/manifest.json
A	artefacts/page-template.html
```

That is the gate. All 6 entry destinations, both protected files and the injected
`artefacts/index.html` are byte-identical to what the prior art committed.

- [ ] **Step 4: Prove the manifest diff is only what was intended**

```bash
PROBE=~/dev/github-kevinlin/artefacts-test
git -C "$PROBE" diff -U0 -- artefacts/manifest.json | grep -c '^+.*"date"'
git -C "$PROBE" diff -U0 -- artefacts/manifest.json \
  | grep -E '^[+-]' | grep -vE '"date"|"replacements"|"favicon"|^(\+\+\+|---)'
```

Expected: `6` dates added, and the remaining lines only the `site` block:

```
+  "site": {
+    "base_url": "https://kevinlin.github.io/artefacts-test/artefacts/",
+    "catalogue": {
+      "mode": "inject",
+      "page": "index.html"
+    }
+  },
```

Any other line is a defect: stop and diagnose it.

- [ ] **Step 5: Prove convergence, and validate**

```bash
python3 -m artefact_sync plan | grep -E '^[A-Z][A-Z ]*\([0-9]+\)'
python3 -m artefact_sync validate > /dev/null; echo "validate=$?"
```

Expected: `EXCLUDED (1)` and `WARNINGS (8)` and no change group at all, then `validate=0`. A second
run that changes nothing is convergence, and it is the half of the gate an entry-by-entry byte
comparison cannot show.

- [ ] **Step 6: Commit the adoption on the probe**

```bash
PROBE=~/dev/github-kevinlin/artefacts-test
git -C "$PROBE" add -A
git -C "$PROBE" commit -m "adopt the artefact-sync skill"
git -C /Users/keli/dev/github-kevinlin/kevinlin.github.io status --short
```

Expected: one commit touching two files, and the profile repository printing nothing.

- [ ] **Step 7: Write the acceptance record**

Create `docs/specs/m4-acceptance.md`, following the shape of
[m2-acceptance.md](m2-acceptance.md): a numbered table with `#`, `Command`, `Expected`, `Result`,
one row per step in Tasks 6 and 7, then a "What the run found" section and a "Result" line. Leave the
remaining rows for Task 8, so the whole gate lives in one document. Include Task 6 Step 1's source
inventory verbatim — the folder is real and mutable, and that table is the only record of what the
gate actually ran against. Record the actual figures, not the predicted ones. State in the opening
paragraph that the gate ran against a probe pair and that `kevinlin.github.io` was neither migrated
nor modified.

- [ ] **Step 8: Apply the corrections to the design**

In `docs/specs/design_artefact-sync.md`, add M4-a to M4-k from this plan's "Corrections to the
design this plan applies" table to the "Changes to the requirement" table, and make these edits in
place:

- "Rendering": state the invariant as text-exact after UTF-8 decode, line-ending normalisation and
  trailing-newline normalisation, and correct "55 doubled-brace escapes" to 36 pairs.
- "Rendering": note that inject mode reuses the fragment markup, so the host page's CSS is what pins
  the class names.
- "Schemas": note that a `dir/` ignore rule matches at any depth, per M4-i.
- "Release ladder": M4's gate is a disposable probe pair, per M4-h; migrating `kevinlin.github.io`
  moves out of the ladder and into a follow-on, with `section_links` (M4-j) and the atlas as its two
  unbuilt prerequisites. Correct "57 real entries" to 56 there and in "Testing".

- [ ] **Step 9: Commit**

```bash
cd /Users/keli/dev/ai-practitioner/artefact-sync
git add docs/specs/m4-acceptance.md docs/specs/design_artefact-sync.md
git commit -m "docs: record the M4 fidelity gate against a prior-art probe tree"
```

---

### Task 8: the live probe — publish, verify, and exercise what the prior art cannot

**Files:**
- Modify: `docs/specs/m4-acceptance.md` (the remaining rows, and the result)
- Modify: `docs/specs/plan_artefact-sync-m4.md` (status line, deviations)
- Adds to `~/Downloads/Claude-Artefacts`: `flow.svg` and `brief.pdf`, plus one temporary
  `dirty.svg` removed in the same step

**Interfaces:**
- Consumes: everything. Produces the release evidence.

This publishes to the internet, on a repository created for the purpose. Nothing here is at risk
beyond the probe. Do not run it until Task 7 produced exactly its expected output.

- [ ] **Step 1: Install the skill and create the probe repository**

```bash
git -C /Users/keli/dev/ai-practitioner/artefact-sync status --short   # must print nothing
ln -s /Users/keli/dev/ai-practitioner/artefact-sync ~/.claude/skills/artefact-sync
ls ~/.claude/skills/artefact-sync/SKILL.md
```

A symlink rather than a clone, so the gate tests the code about to be tagged rather than a copy of
it. Distribution by `git clone` is unchanged for everyone else.

```bash
PROBE=~/dev/github-kevinlin/artefacts-test
gh repo create kevinlin/artefacts-test --public --source "$PROBE" --remote origin --push
```

Then enable Pages in the repository settings: Settings, Pages, source `Deploy from a branch`, branch
`main`, folder `/ (root)`. Wait for the first build, then confirm the URL the skill will use:

```bash
python3 -m artefact_sync init \
  --repo ~/dev/github-kevinlin/artefacts-test \
  --source ~/Downloads/Claude-Artefacts
```

Expected: `pointer written to ~/.config/artefact-sync/config.json`, `seeded .../artefacts`, and
`verified https://kevinlin.github.io/artefacts-test/artefacts/`. `init` creates nothing that already
exists, so the manifest, the template and the vendored JS are all left alone. A 404 means Pages has
not finished its first build; wait and re-run. A URL missing the `artefacts-test` segment means
`base_url` in the manifest is wrong — fix the manifest, not the code.

- [ ] **Step 2: Publish, and verify every URL**

```bash
time python3 -m artefact_sync publish
```

Expected: nothing left to apply after Task 7, so this reaches `nothing to publish; 10 published URLs
verified.` — the base URL, `index.html`, 6 entries and 2 protected files. If Task 7's commit has not
been pushed yet, `publish` pushes it, waits for the Pages build and then verifies. Record the
wall-clock time against M2's 39 seconds for 6 URLs.

- [ ] **Step 3: Check the probe in a browser**

Open `https://kevinlin.github.io/artefacts-test/artefacts/` and confirm:

- The catalogue renders with the host page's own CSS: cards in a grid, `Updated` dates present.
  That is Task 3's markup fitting a stylesheet it never saw.
- `showcase/index.html` still serves its hand-written text, untouched.
- `star-wars-timeline/` and `coding-agent-adoption/` render, and their literal `</script>` text, em
  dashes and entities all survived `transform_html`.
- One Markdown page — `mingpt-vs-toy-transformer/analysis/` — renders through `marked.js` with no
  console messages. This is the page the `$prefix$vendor` fix exists for: at depth 2 it loads
  `../../vendor/marked.min.js`, and a blank page here means Task 1 regressed.
- `mingpt-vs-toy-transformer/infographic.png` loads at full size.

- [ ] **Step 4: Compare served bytes against source bytes**

M2 did this by hand for two files, and the design records the gap it closes: nothing in `publish`
proves the bytes GitHub serves equal the bytes pushed.

```bash
python3 - <<'PY'
import hashlib, json, urllib.request
from pathlib import Path
base = "https://kevinlin.github.io/artefacts-test/artefacts/"
source = Path.home() / "Downloads/Claude-Artefacts"
manifest = json.loads(
    (Path.home() / "dev/github-kevinlin/artefacts-test/artefacts/manifest.json")
    .read_text(encoding="utf-8")
)
for entry in manifest["entries"]:
    if Path(entry["source"]).suffix.lower() not in {".png", ".jpeg", ".jpg"}:
        continue
    served = urllib.request.urlopen(base + entry["destination"], timeout=30).read()
    local = (source / entry["source"]).read_bytes()
    mark = "same" if hashlib.sha256(served).digest() == hashlib.sha256(local).digest() else "DIFFER"
    print(f"{mark}  {entry['destination']}  {len(served):,} bytes")
PY
```

Expected: `same` for `mingpt-vs-toy-transformer/infographic.png`, 2,130,205 bytes. A 2 MB image
round-tripping intact through push and Pages is worth having on the record.

- [ ] **Step 5: Publish what the prior art never could**

The gate proves fidelity on the surface both implementations share. The skill's own additions —
`.svg`, `.pdf`, `.webp`, `.gif`, and the SVG validator — have no prior-art counterpart, so they come
after the green run, exactly as the design says intentional changes should. These two files are added
to a real folder; both are named here and can be deleted afterwards.

```bash
cat > ~/Downloads/Claude-Artefacts/flow.svg <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 40">
  <rect width="100" height="40" fill="#eee"/>
  <text x="50" y="24" text-anchor="middle" font-size="10">flow</text>
</svg>
EOF
printf '%%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%%%EOF\n' \
  > ~/Downloads/Claude-Artefacts/brief.pdf
python3 -m artefact_sync plan | grep -E '^[A-Z][A-Z ]*\([0-9]+\)|^  '
```

Expected: exit 3, `BLOCKED (2)` naming both files as `approved source has no manifest entry;
proposal generated`, and `NEW PUBLIC URLS (2)` with their sizes. A closed allowlist stopping to ask
about two files the user just added is correct behaviour, and it is the two-step flow M3 built: the
first run proposes, the second publishes.

Review the proposed entries, then publish them:

```bash
python3 -m artefact_sync publish
```

Expected: the confirmation names both new URLs and the irreversibility, then 12 URLs verified. Open
`flow.svg` in a browser and confirm it renders.

Then prove the SVG gate rejects rather than rewrites:

```bash
cat > ~/Downloads/Claude-Artefacts/dirty.svg <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
  <script>alert(1)</script>
</svg>
EOF
python3 -m artefact_sync plan | grep -A3 '^BLOCKED'
rm ~/Downloads/Claude-Artefacts/dirty.svg
```

Expected: `BLOCKED` naming `dirty.svg:2` and `script element`, exit 3, and nothing written.

- [ ] **Step 6: Exercise a deletion and reconverge**

Delete a file the skill added in Step 5 rather than anything that was in the folder to begin with:

```bash
rm ~/Downloads/Claude-Artefacts/brief.pdf
python3 -m artefact_sync publish
```

Expected: the confirmation says exactly one URL will start returning 404; after the build that URL
404s, the others still serve, and the catalogue dropped its link. No orphan warning names the file
being deleted — that is M3's fix holding on a live run.

Then confirm a re-run is a no-op:

```bash
python3 -m artefact_sync publish
```

Expected: `no changes.` and `nothing to publish; 11 published URLs verified.`

- [ ] **Step 7: Finish the record and commit**

Fill in the remaining rows of `docs/specs/m4-acceptance.md` from Steps 1-6, write its "What the run
found" and "Result" sections, set this plan's status line, and fill in "Deviations from this plan"
with every place the plan was wrong, corrected test counts included. Record in a "Teardown" section
what was left behind: whether `flow.svg` stayed in `~/Downloads/Claude-Artefacts`, and whether the
probe repository was kept. Keeping the repository is worth more than deleting it, because the next
milestone gets a live target for free; if it is deleted, `gh repo delete` needs an interactive
`gh auth refresh -h github.com -s delete_repo` first, as M2 found.

```bash
cd /Users/keli/dev/ai-practitioner/artefact-sync
git add docs/specs/m4-acceptance.md docs/specs/plan_artefact-sync-m4.md
git commit -m "docs: record the M4 release gate on the artefacts-test probe"
git -C /Users/keli/dev/github-kevinlin/kevinlin.github.io status --short
```

Expected: the last command prints nothing, for the last time.

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

## Warnings

- **The profile repository is read-only for the whole milestone.** No branch, no commit, no edit to
  `scripts/artefacts.py` or `validate-artefacts.yml`. Task 6 copies the script out and runs the copy
  with `python3 -B`. Check `git -C /Users/keli/dev/github-kevinlin/kevinlin.github.io status
  --short` after every task.
- **`~/Downloads/Claude-Artefacts` is a real folder.** Tasks 6 and 7 read it. Task 8 adds `flow.svg`
  and `brief.pdf` and removes a temporary `dirty.svg`. Nothing else in it is touched, and the
  inventory in Task 6 Step 1 is what proves that afterwards.
- **Task 6 Step 3 must run before the skill ever touches the probe.** The gate is only worth
  anything if the prior art wrote the baseline. If the skill publishes first, the comparison is the
  skill against itself and proves nothing.
- **Do not "fix" a published page to make a diff go away.** All four code fixes exist because the
  tool rendered something differently from what was published. If a fifth difference appears, find
  out which side is wrong before changing either.
- **Use `git diff HEAD`, never `git status`, for every claim about what moved.** With
  `core.autocrlf = input`, status can report a working-tree line-ending change whose commit diff is
  empty.
- **Do not shorten an `ignored_sources` rule during adoption.** A bare `dir/` rule matches at any
  depth in the skill and only at the root in the prior art, so shortening one silently drops files
  that were being published. M4-i.

---

## Self-Review

**Spec coverage.** Walked the design's M4 paragraph and every section the gate touches.

| Spec item | Task |
|---|---|
| "Copy the existing template verbatim into `page-template.html`" | 7 Step 1, with the conversion proven by every Markdown page coming out byte-identical |
| "Seed `date` from current mtimes" | Already built: `plan._stamp_missing_dates` runs inside `create_sync_plan`. Verified in 7 Step 4 as 6 date lines |
| "Install the skill" | 8 Step 1 |
| "Run `plan` against the live tree, and require zero changes" | 7 Step 2. One change, `manifest.json`, and it is the stamped dates |
| "An empty plan across real entries proves the extraction preserved behaviour" | 7 Step 3 proves it as a staged git diff, which is stronger than a plan group: it covers protected files and the injected catalogue, which no plan group reports. 7 Step 5 adds convergence |
| "Drift in escaping, catalogue rendering, ordering or transformation all show up as a non-empty plan" | Found four such drifts. Escaping: Task 2. Catalogue rendering and ordering: Task 3. Transformation: Task 1 |
| "M2: the disposable Pages repo is the provider seam's only real test" | 8 extends that to 12 URLs, a deletion, a rejected SVG, and a 2 MB served-bytes comparison |
| D5: `init` writes `vendor/marked.min.js` and `page-template.html` into the repo | 8 Step 1. Both already exist, so `init` skips them |
| Invariant 1: an existing entry is never re-titled or re-slugged | Enforced throughout, and Task 4 is what keeps it enforced during adoption rather than silently disabled |
| Invariant 2: `destination` is frozen once published | Same. 7 Step 3 proves no destination moved |
| Invariant 4: orphans are never deleted | 7 Step 2: zero orphan warnings, because every file in the probe tree is an entry, a protected file, or a reserved name. 8 Step 6 re-proves M3's fix on a live deletion |
| Closed allowlist has three distinct outcomes | 7 Step 2's `EXCLUDED` shows the ignored outcome; 8 Step 5 shows approved-but-unlisted blocking. The unsupported-suffix outcome is not in this corpus — see the coverage table |
| "`.svg` behind a validator: reject and name the line, never rewrite" | 8 Step 5 |
| "Post-push URL verification is the only proof a publish worked" | 8 Steps 2, 4 and 6 |

**Deliberately not done, and why.**

- **`kevinlin.github.io` is not migrated.** Deferred by the milestone's owner. Most of what that
  migration needs lands here; what it still needs is in "After M4", with the measurement.
- **`site.catalogue.section_links` is not built.** M4-j. The probe corpus yields one section and no
  showcase link, so nothing in this milestone would exercise it. It is the live migration's
  requirement, and building it now would ship an unexercised feature.
- **No second page template and no catalogue templating engine.** The fragment markup is now the
  prior art's, and a host page adapts by styling those class names. A fragment template would need
  loops over sections, cards and items, which `string.Template` cannot express.
- **The corpus was not padded to cover more paths.** Generating files to hit CRLF, an unsupported
  suffix and a secret shape would make the gate test the fixture rather than the tool. Those paths
  are covered by unit tests and by `test_m4_adoption.py`, and the coverage table says which.
- **The probe does not exercise `replacements`.** No live entry uses it either.
- **No `.gitattributes` in the probe.** Setting `artefacts/** -text` would stop git normalising and
  keep bytes exact, but it fixes one repository and leaves the tool broken for the next adopter
  whose git normalises. Task 1 fixes the tool.
- **No version bump.** The design accepts that `manifest.version` has no source of truth. M4 adds
  no manifest key at all, so an old manifest still loads.

**Type consistency.** `normalise_source_text(source_bytes: bytes, label: str) -> str` has one
signature across its definition in `render.py` and its three callers (`render_markdown_page`,
`transform_html`, `apply.verify_markdown_round_trip`). `render_catalogue(manifest, site)` keeps the
signature `catalogue.render_standalone_catalogue`, `plan.create_sync_plan` and `validate` already
call, and still takes `site` even though it no longer reads a field off it — changing the signature
would touch three callers for nothing. `section_slug(value: str) -> str` is defined and called only
inside `catalogue.py`. `catalogue.entry_sort_key` and `catalogue._invert` are deleted, and
`tests/test_catalogue.py::SortTests` — their only caller — goes with them.
`head_manifest(repo_root) -> Manifest | None` is unchanged in signature, so `cli._command_state` and
every publish path are untouched. `BLOCK_START` and `BLOCK_END` keep their names; only
`BLOCK_START`'s value moves. `config.Site` is untouched, so every positional construction in
`selfcheck.py` and the tests keeps working.

**Predicted counts.** 227 at the start, then 232, 233, 240, 242, 246. Tasks 6, 7 and 8 add no tests.
Every number is a prediction; see the last global constraint.

**Known test churn.** Four existing tests fail once Tasks 1-3 land, and each is rewritten by the
task that breaks it: `test_catalogue.SortTests` (2, Task 3, `entry_sort_key` deleted) and
`test_render_markdown.TemplateTests::test_the_renderer_reads_the_embedded_source_block_id` and
`::test_the_browser_does_not_strip_a_leading_source_newline` (2, Task 2). No other test in the suite
changes behaviour. If a fifth breaks, that is a finding.

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
