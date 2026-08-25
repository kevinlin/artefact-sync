# artefact-sync M4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the release gate. Migrate `kevinlin.github.io` off `scripts/artefacts.py` and onto
the skill, and require that every one of its 56 published URLs keeps serving the same bytes.

**Architecture:** No new modules. M4 is four small corrections inside `render.py`, `catalogue.py`,
`config.py` and `manifest.py`, all four found by running the skill against the live tree before
writing this plan. Then a dry run against a throwaway clone, then the live cutover. The four
corrections are measured, not guessed: with them applied to a scratch copy, all 56 published entry
blobs and `artefacts/index.html` come out byte-identical, and the only file that changes is
`artefacts/manifest.json`.

**Tech Stack:** Python 3.9, standard library only, `unittest`. Tasks 1-5 run offline. Tasks 6-8 touch
a real repository and the network.

**Spec:** [design_artefact-sync.md](design_artefact-sync.md), release ladder line "M4: release gate,
migrating `kevinlin.github.io`", and the "Release ladder" section's M4 paragraph. Supporting evidence
with `file:line` citations into the prior art is
[extraction-analysis.md](../research/extraction-analysis.md). The three earlier milestones and the
deviations this plan inherits are [plan_artefact-sync-m1.md](plan_artefact-sync-m1.md),
[plan_artefact-sync-m2.md](plan_artefact-sync-m2.md),
[plan_artefact-sync-m3.md](plan_artefact-sync-m3.md), and the live evidence from M2 is
[m2-acceptance.md](m2-acceptance.md).

## Global Constraints

Every task's requirements implicitly include this section. The first ten carry over from M3.

- **Python 3.9.** The tool must run under stock macOS `/usr/bin/python3` (3.9.6). Every module
  starts with `from __future__ import annotations` so `X | None` annotations parse on 3.9.
- **Standard library only.** No third-party import in the shipped package or in its tests, ever.
  `tests/test_stdlib_only.py` already allows every module M4 needs (`re`, `string`, `json`,
  `dataclasses`); do not widen `ALLOWED`.
- **Test command:** `python3 -m unittest discover -s tests -t . -v`. Never pytest. Run it under
  **both** `python3` (3.13) and `/usr/bin/python3` (3.9.6) before every commit.
- **The M3 baseline is 227 tests, all passing on both interpreters.** No task may leave that number
  lower.
- **British spelling** in every user-facing string, path and identifier: `artefacts`, `catalogue`.
- **No emoji** in any output. `tests/test_plan.py::test_no_emoji_anywhere_in_the_output` enforces it
  for `format_plan`; keep it passing.
- **The shipped assets carry no branding.** `tests/test_render_markdown.py`
  ::`test_the_shipped_template_carries_no_branding` forbids `kevin`, `kevinlin` and `github.io` in
  `artefact_sync/assets/page-template.html`. M4 copies the site's template into the *site's*
  repository, never into `assets/`. Keep that test passing.
- **Exit codes:** `0` success, `1` error, `3` blocked and needs a human decision.
- **No network in the unit suite.** Tasks 1-5 add no networked code path.
- **Never write to `/Users/keli/dev/github-kevinlin/kevinlin.github.io` before Task 8.** Tasks 1-6
  read it and write only to a clone. `git -C /Users/keli/dev/github-kevinlin/kevinlin.github.io
  status --short` must print nothing at the end of every task up to and including Task 6.
- **Every test count in this plan is a prediction.** M2 and M3 both recorded cases where a stated
  count was satisfied by contorting the code instead of correcting the number. If your count
  differs, the number here is wrong: fix it in "Deviations from this plan". Never merge two distinct
  failures into one `subTest` loop, and never build a test name by string concatenation, to hit a
  figure written before the code existed.
- **The measurements in this plan were taken against the tree as of live-repo HEAD `280b17e`.** If
  the live repository or `~/Downloads/Artefacts` has moved on, re-measure with the commands in
  Task 6 Step 1 before trusting a count.

---

## What M4 actually is

The design's ladder line reads "M4: release gate, migrating `kevinlin.github.io`", and the "Release
ladder" section spells out the procedure: copy the template verbatim, seed `date` from mtimes,
install the skill, run `plan`, require zero changes. Running that procedure before writing this plan
found four defects. All four are in the skill, none in the site, and each one silently rewrites live
content.

| # | What breaks | Blast radius on the live tree | Task |
|---|---|---|---|
| 1 | `render_markdown_page` bakes the `../` climb into `$vendor`, and the design's template also uses `$prefix`, so a template using both — as the site's does — doubles the climb | All 9 Markdown pages get a broken `<script src>`; `validate` catches it as `broken local reference` | 1 |
| 2 | Neither `render_markdown_page` nor `transform_html` normalises line endings, and `core.autocrlf=input` strips CR on commit, so the tree `apply` writes is not the tree git stores | 1 page today (`agent-harness/20260713-loop-engineering-raw/index.html`, 16 CRs), and any future CRLF source. A fresh clone never converges: `plan` reports the same entry CHANGED forever | 1 |
| 3 | The embedded block is `id="artefact-source"` with no leading newline; every published page carries `id="markdown-source"` and a newline | All 9 Markdown pages rewritten for no reason. `extract_markdown` also cannot read any page published by the prior art, so `plan` prints `diff unavailable: page has no embedded Markdown` instead of a diff | 2 |
| 4 | `catalogue.render_catalogue` emits its own markup and sorts entries by date; the live `index.html` CSS targets `card-grid`, `card` and `card-updated`, sorts *cards* by date and *entries* by `order`, and hangs the 3D showcase link off one section heading | The whole 221-line catalogue replaced with unstyled markup; card order changes in 2 of 2 sections, entry order in 4 of 21 cards; the showcase link disappears and the 3D gallery becomes unreachable | 3 |

Plus one migration blocker that is nobody's defect but stops the first run dead:

| # | What breaks | Task |
|---|---|---|
| 5 | `manifest.head_manifest` parses `git show HEAD:artefacts/manifest.json` through the full strict schema, so in any repository whose committed manifest predates the `site` block the first command exits with `missing manifest field: site` — naming a field the user has already set in the working copy | 4 |

### The live tree, measured

Numbers this plan relies on. Every one came from a read-only run; the commands are in Task 6 Step 1.

| Fact | Value |
|---|---|
| Manifest entries | **56** (the requirement and design both say 57) |
| Collections | 31, of which 21 have entries and render |
| `protected_files` | 36 |
| Files under `artefacts/` | 96 = 56 entries + 36 protected + `index.html` + `manifest.json`, plus 2 untracked `.DS_Store` |
| Source files under `~/Downloads/Artefacts` | 234 |
| Approved by suffix | 128 |
| Left after `ignored_sources` | 66 |
| Approved but unlisted | **10**, all under `.firecrawl/` |
| Entry source suffixes | 26 `.png`, 14 `.html`, 9 `.md`, 5 `.jpeg`, 2 `.jpg` |
| Doubled-brace pairs in the prior art's `MARKDOWN_PAGE_TEMPLATE` | **36** (the design says 55) |
| `$` characters in that template | 0, so the `string.Template` conversion needs no `$$` escaping |

The 10 unlisted files are the whole reason a first run blocks: `scan_source` in the prior art skips
any directory whose name starts with `.` (`artefacts.py:463`), the skill does not, and the live
`ignored_sources` predates the `.*` seed that `cli.SEED_IGNORES` now carries. One added rule fixes
it.

---

## Corrections to the design this plan applies

Each was found by running the skill against the live tree. Apply each to
[design_artefact-sync.md](design_artefact-sync.md) as M1, M2 and M3 did.

| # | What the design or the code says | What M4 does | Why |
|---|---|---|---|
| M4-a | Template placeholders are `$title, $favicon, $prefix, $vendor, ...` | `$vendor` is the vendor path alone; `$prefix` is the `../` climb; the shipped template composes `src="$prefix$vendor"` | `render_markdown_page` passes `vendor=prefix + vendor_path`, and the shipped template uses `$vendor` on its own, so the two placeholders cannot both be used as documented. The site's template uses both and gets `../../../../vendor/marked.min.js` |
| M4-b | E5: the invariant is "text-exact after UTF-8 decode and trailing-newline normalisation" | Text-exact after UTF-8 decode, **line-ending normalisation**, and trailing-newline normalisation | Git with `core.autocrlf=input` — the setting on this machine, and a common default — stores LF for a CRLF working-tree file. Without normalisation the bytes `apply` writes are not the bytes that get published, and a fresh clone reports the same entry CHANGED on every run, forever. Normalising CRLF to LF is safe for Markdown: a hard line break is trailing spaces or a backslash, never a CR |
| M4-c | The Markdown block is `<script type="text/markdown" id="artefact-source">` | `<script type="text/markdown" id="markdown-source">` followed by a newline | The prior art published 9 pages with `markdown-source` and a leading newline (`artefacts.py:525-526`). Keeping the skill's spelling rewrites all 9 for no gain, and `extract_markdown` cannot read a page the prior art published, so the diff preview and `apply`'s round-trip check both go blind on exactly the pages a migration needs to check |
| M4-d | "`date` lets the catalogue sort by recency instead of hand-maintained `order`" | Collection **cards** sort by their newest entry date, descending, stable on `order`. **Entries** inside a card keep sorting by `order` | The prior art sorts cards by recency and entries by `order` (`artefacts.py:1360-1383`). Sorting entries by date too reorders 4 of the 21 live cards, and it is the wrong reading anyway: a card's date answers "is this collection fresh", while an entry's position inside a card is editorial |
| M4-e | "Customising the standalone catalogue means adding markers to it and switching to inject mode, so there is no second template" | True for the shell, false for the fragment. `render_catalogue` adopts the prior art's markup, and `site.catalogue.section_links` maps a section title to raw HTML appended inside its `<h2>` | The fragment's class names are what the host page's CSS targets, so a host page cannot adopt a foreign fragment without a rewrite. The site's 3D showcase link lives inside one section heading and is regenerated on every sync, so without a hook the migration deletes the only route to the 3D gallery. One optional map, read in one line, and the raw HTML is the user's own manifest — the same trust level as `favicon` and `replacements` |
| M4-f | `head_manifest` returns "the manifest as of HEAD, or None when it was never committed" | Also `None` when HEAD's manifest cannot be parsed, after one attempt with a placeholder `site` injected | A repository adopting the skill has a committed manifest with no `site` block, and the invariant check reads only `id`, `destination` and `title` from it. Failing the whole run on a field the check never touches makes adoption impossible; returning `None` immediately would throw away the URL-freeze guard on precisely the run where 56 live destinations are at stake. Injecting a placeholder keeps the guard and lets the run proceed |
| M4-g | `HOMEPAGE_FILES` is part of the site-coupling surface still to port | Not ported | It backs a `git diff --exit-code base...HEAD -- index.html styles.css script.js` check. `publish`'s preflight already refuses any change outside `artefacts/`, which is strictly stronger and needs no base ref |
| M4-h | Migration rehomes the atlas as "a git hook, or a step in its own workflow" | A documented manual step in the site's `CLAUDE.md`, `AGENTS.md` and `README.md` | `build_showcase_atlas.py` shells out to `ffmpeg`, so a CI staleness check compares JPEG bytes from two different encoder builds and fails on every run. A git hook is not versioned and does not survive a clone. The migration itself changes zero published images, so nothing is stale on day one; only a future image add needs the step |
| M4-i | "57 real entries" (requirement and design) | 56 | Counted. `manifest.json` carries 56 entries |

---

## File Structure

```
artefact-sync/
  SKILL.md                          + section_links in the manifest shape,
                                    + "Adopting an existing artefacts tree"
  artefact_sync/
    render.py                       + normalise_source_text, BLOCK_START, vendor placeholder
    apply.py                        verify_markdown_round_trip uses normalise_source_text
    catalogue.py                    prior-art markup, section_slug, card ordering, section_links
    config.py                       Site.section_links, site_from_dict, site_to_dict
    manifest.py                     head_manifest tolerates a pre-site HEAD manifest
    assets/page-template.html       src="$prefix$vendor", markdown-source, leading-newline strip
    assets/catalogue-template.html  CSS renamed to .card-grid / .card / .card-updated
  tests/
    test_render_markdown.py         + CRLF cases, block-id cases rewritten
    test_render_html.py             + CRLF case
    test_apply.py                   + CRLF round trip, block-id literal updated
    test_catalogue.py               SortTests rewritten as CardOrderTests, + markup, + section_links
    test_config.py                  + section_links round trip
    test_manifest_invariants.py     + a HEAD manifest with no site block
    test_m4_adoption.py    NEW      adopting a tree that already has published files
  docs/specs/
    m4-acceptance.md       NEW      the dry run and the live cutover, recorded
    plan_artefact-sync-m4.md        this file: status line and deviations, at the end
    design_artefact-sync.md         corrections M4-a to M4-i
```

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
  `render_markdown_page` substitutes `vendor=vendor_path.as_posix()` and any template must write
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
        # A template using both, as the design documents and the migrated site does.
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
`test_a_lone_carriage_return_normalises_to_lf` fails, `test_prefix_and_vendor_are_separate_placeholders`
fails (`../../|../../vendor/...`), and `test_a_crlf_source_still_verifies_against_the_lf_page` passes
already because nothing normalises yet on either side. `test_the_shipped_template_climbs_to_the_vendor_file`
passes for the wrong reason and will keep passing.

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

In `artefact_sync/apply.py`, replace the head of `verify_markdown_round_trip`:

```python
def verify_markdown_round_trip(source_bytes: bytes, rendered: bytes, label: str) -> None:
    from .render import normalise_source_text

    try:
        expected = normalise_source_text(source_bytes, label)
        document = rendered.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(f"{label}: markdown round trip is not UTF-8 ({error})") from error
    found = extract_markdown(document)
```

`apply.py` already imports `extract_markdown` from `.render` at module level; move
`normalise_source_text` onto that import line rather than importing inside the function:

```python
from .render import extract_markdown, normalise_source_text
```

and drop the local import. `TransformationError` from `normalise_source_text` is not a
`ValidationError`, so let it propagate: a source that stopped being UTF-8 between plan and apply is
a transformation failure, and the message already names the file.

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

Expected: OK on both, 231 tests.

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
        # nine live pages for nothing. See M4-c.
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

Expected: OK on both, 232 tests.

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
- Modify: `artefact_sync/config.py` (`Site.section_links`, `site_from_dict`, `site_to_dict`)
- Modify: `artefact_sync/assets/catalogue-template.html` (CSS class names)
- Test: `tests/test_catalogue.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `manifest.Manifest`, `manifest.Collection`, `manifest.Entry`, `config.Site`,
  `config.site_from_dict`, `config.site_to_dict`, `catalogue.replace_generated_catalogue`,
  `catalogue.render_standalone_catalogue`, `catalogue.public_href`.
- Produces: `catalogue.section_slug(value: str) -> str`; `catalogue.render_catalogue(manifest, site)`
  keeps its signature and returns the prior art's markup; `config.Site` gains
  `section_links: dict[str, str]`, defaulting to `{}`, read from
  `site.catalogue.section_links` and re-emitted by `site_to_dict` only when non-empty.
  `catalogue.entry_sort_key` and `catalogue._invert` are **removed**; nothing outside
  `tests/test_catalogue.py` calls them.

- [ ] **Step 1: Write the failing tests**

Replace `class SortTests` in `tests/test_catalogue.py` with the following, and extend the module's
helpers so a test can build more than one collection. Replace the `build` helper and add
`collection`:

```python
def collection(**overrides) -> Collection:
    body = dict(id="c", title="C", description=None, section="S", section_order=10, order=10)
    body.update(overrides)
    return Collection(**body)


def build(entries, collections=None, site=None) -> Manifest:
    return Manifest(
        version=1, site=site or SITE, protected_files=(), ignored_sources=(),
        collections=tuple(collections or (collection(),)),
        entries=tuple(entries),
    )
```

Then:

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
        fragment = catalogue.render_catalogue(build([entry()]), SITE)
        self.assertNotIn("card-updated", fragment)

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


class SectionLinkTests(unittest.TestCase):
    def test_a_configured_section_link_rides_its_heading(self) -> None:
        site = site_from_dict({
            "base_url": "https://x.example/artefacts/",
            "catalogue": {"mode": "standalone",
                          "section_links": {"S": '\n<a href="showcase/">3D</a>\n'}},
        })
        fragment = catalogue.render_catalogue(build([entry()], site=site), site)
        self.assertIn('<h2 id="s-heading">S\n<a href="showcase/">3D</a>\n</h2>', fragment)

    def test_a_link_for_an_absent_section_changes_nothing(self) -> None:
        site = site_from_dict({
            "base_url": "https://x.example/artefacts/",
            "catalogue": {"mode": "standalone", "section_links": {"Nowhere": "<b>x</b>"}},
        })
        self.assertNotIn("<b>x</b>", catalogue.render_catalogue(build([entry()], site=site), site))
```

The module needs one more import for `SectionLinkTests`; the existing line
`from artefact_sync.config import site_from_dict` already provides it.

Add to `tests/test_config.py`:

```python
class SectionLinkTests(unittest.TestCase):
    def test_section_links_round_trip_through_the_site_block(self) -> None:
        raw = {"base_url": "https://x.example/artefacts/",
               "catalogue": {"mode": "inject", "page": "index.html",
                             "section_links": {"Images": "<a href='s/'>3D</a>"}}}
        site = config.site_from_dict(raw)
        self.assertEqual({"Images": "<a href='s/'>3D</a>"}, site.section_links)
        self.assertEqual(raw["catalogue"], config.site_to_dict(site)["catalogue"])

    def test_an_empty_section_link_map_is_omitted_from_the_emitted_json(self) -> None:
        site = config.site_from_dict({"base_url": "https://x.example/artefacts/"})
        self.assertNotIn("section_links", config.site_to_dict(site)["catalogue"])
```

`tests/test_config.py` already has `from artefact_sync import config`, which is what these two cases
use. Add no import.

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest tests.test_catalogue tests.test_config -v`
Expected: every new `MarkupTests`, `CardOrderTests`, `EntryOrderTests` and `SectionLinkTests` case
fails, and both `test_config.py` cases fail with `TypeError` or `AttributeError` on
`section_links`. `InjectionTests` and `StandaloneTests` keep passing.

- [ ] **Step 3: Give `Site` a `section_links` map**

In `artefact_sync/config.py`, change the import and the dataclass:

```python
from dataclasses import dataclass, field
```

```python
@dataclass(frozen=True)
class Site:
    base_url: str
    favicon: str
    catalogue_mode: str
    catalogue_page: PurePosixPath | None
    section_links: dict = field(default_factory=dict)
```

The default matters: `selfcheck.PROBE_SITE` and several tests build `Site` positionally with four
arguments and must keep working.

In `site_from_dict`, before the `return`:

```python
    links = catalogue.get("section_links") or {}
    if not isinstance(links, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in links.items()
    ):
        raise ConfigError("site.catalogue.section_links must map section titles to HTML strings")
```

and add `section_links=dict(links),` to the `Site(...)` call.

In `site_to_dict`, after the `page` line:

```python
    if site.section_links:
        catalogue["section_links"] = dict(site.section_links)
```

- [ ] **Step 4: Rewrite `render_catalogue`**

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
        heading = html.escape(section_title) + site.section_links.get(section_title, "")
        lines.extend(
            [
                f'        <section aria-labelledby="{heading_id}">',
                f'            <h2 id="{heading_id}">{heading}</h2>',
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

- [ ] **Step 5: Restyle the bundled standalone catalogue**

In `artefact_sync/assets/catalogue-template.html`, replace the two class rules with three that match
the new markup:

```css
        .card-grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); }
        .card { padding: 1rem; border: 1px solid #ddd; border-radius: 0.5rem; }
        .card-updated { color: #666; font-size: 0.875rem; }
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_catalogue tests.test_config -v`
Expected: PASS.

Then both interpreters:

```bash
python3 -m unittest discover -s tests -t . 2>&1 | tail -3
/usr/bin/python3 -m unittest discover -s tests -t . 2>&1 | tail -3
```

Expected: OK on both, 244 tests. `tests/test_m1_end_to_end.py` and `tests/test_m3_end_to_end.py`
assert `"cost-model/"` and similar hrefs are present in the catalogue, which the new markup still
satisfies. If either fails on markup rather than on an href, fix the assertion, not the markup.

- [ ] **Step 7: Commit**

```bash
git add artefact_sync/catalogue.py artefact_sync/config.py \
        artefact_sync/assets/catalogue-template.html \
        tests/test_catalogue.py tests/test_config.py
git commit -m "feat(catalogue): emit styleable markup, order cards by date, hook section links"
```

---

### Task 4: `head_manifest` survives a HEAD that predates the `site` block

**Files:**
- Modify: `artefact_sync/manifest.py:358-367` (`head_manifest`)
- Test: `tests/test_manifest_invariants.py`

**Interfaces:**
- Consumes: `manifest.head_manifest`, `manifest.check_published_invariants`,
  `manifest.manifest_from_dict`, `manifest.manifest_to_json`, `tests.helpers.make_repo`.
- Produces: no signature change. `head_manifest` returns `None` for an unparseable HEAD manifest
  instead of raising, and parses one that lacks `site` by injecting a placeholder before validating.
  `check_published_invariants` therefore still sees real `id`/`destination`/`title` values from a
  manifest written before the `site` block existed.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_manifest_invariants.py`:

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
            self.assertEqual(("a/index.html",), tuple(
                e.destination.as_posix() for e in head.entries))

    def test_an_unreadable_head_manifest_leaves_the_invariants_unchecked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp), {"artefacts/manifest.json": b"not json at all\n"})
            self.assertIsNone(m.head_manifest(repo))
```

`tempfile`, `Path` and `make_repo` are already imported in that module, and it binds the package as
`m`. Add `import json` at the top; add nothing else.

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest tests.test_manifest_invariants -v`
Expected: `test_a_head_manifest_without_a_site_block_still_freezes_destinations` fails with
`ValidationError: missing manifest field: site`, and
`test_an_unreadable_head_manifest_leaves_the_invariants_unchecked` fails with
`ValidationError: cannot read manifest`.

- [ ] **Step 3: Make the HEAD read lenient**

In `artefact_sync/manifest.py`, replace the tail of `head_manifest`:

```python
def head_manifest(repo_root: Path) -> Manifest | None:
    """The manifest as of HEAD, or None when it was never committed or cannot be read.

    Read leniently on purpose. This value only ever feeds `check_published_invariants`,
    which reads `id`, `destination` and `title`. A repository adopting the skill has a
    committed manifest with no `site` block, so failing the whole run on a field the
    check never touches would make adoption impossible — while returning None outright
    would drop the URL-freeze guard on exactly the run where live destinations are at
    stake. Injecting a placeholder keeps the guard.
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

Expected: OK on both, 246 tests.

- [ ] **Step 5: Commit**

```bash
git add artefact_sync/manifest.py tests/test_manifest_invariants.py
git commit -m "fix(manifest): adopt a repo whose committed manifest predates the site block"
```

---

### Task 5: adopting a tree that already has published files, and `SKILL.md`

**Files:**
- Create: `tests/test_m4_adoption.py`
- Modify: `SKILL.md`

**Interfaces:**
- Consumes: everything Tasks 1-4 produced, plus `cli.main`, `cli.EXIT_OK`,
  `tests.helpers.make_repo`, `tests.helpers.make_source_tree`. Adds no new interface.

This is the offline stand-in for Task 6. Task 6 runs the real thing once; this test runs the same
shape on every commit forever, so the four fixes cannot silently regress after the gate is green.

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
CRLF_NOTE = b"# Cost model\r\n\r\nBuild versus buy."
PAGE = b"<html><head><title>P</title></head><body>Hi</body></html>\n"


def _seed_published_tree(repo: Path, source: Path) -> Path:
    """Publish once, commit, and hand back the manifest path.

    Committing matters: git normalises CRLF on commit under core.autocrlf=input, so
    the committed bytes are what a second machine — or a fresh clone — would see.
    """
    pointer = repo.parent / "pointer.json"
    cli.main(["init", "--pointer", str(pointer), "--repo", str(repo), "--source", str(source)])
    cli.main(["plan", "--pointer", str(pointer)])
    cli.main(["sync", "--pointer", str(pointer), "--yes"])
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin"}
    for args in (["add", "-A"], ["commit", "-q", "-m", "publish"]):
        subprocess.run(["git", *args], cwd=repo, env=env, check=True)
    return pointer


class AdoptionTests(unittest.TestCase):
    def test_a_published_tree_is_not_rewritten_on_re_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"note.md": CRLF_NOTE, "page.html": PAGE})
            pointer = _seed_published_tree(repo, source)

            # Adoption from a clean checkout: nothing left to do, nothing to rewrite.
            self.assertEqual(cli.EXIT_OK, cli.main(["plan", "--pointer", str(pointer)]))
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            self.assertEqual("", subprocess.run(
                ["git", "status", "--short"], cwd=repo, capture_output=True, text=True,
            ).stdout)

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
            # Rewrite HEAD's manifest to the pre-site shape, as a real adopter's is.
            path = repo / "artefacts" / "manifest.json"
            body = json.loads(path.read_text(encoding="utf-8"))
            body.pop("site")
            path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
            env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                   "PATH": "/usr/bin:/bin:/usr/local/bin"}
            for args in (["add", "-A"], ["commit", "-q", "-m", "pre-site manifest"]):
                subprocess.run(["git", *args], cwd=repo, env=env, check=True)
            # Put the site block back in the working copy only, as the migration does.
            body["site"] = {"base_url": "https://x.example/artefacts/",
                            "catalogue": {"mode": "standalone"}}
            path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(cli.EXIT_OK, cli.main(["plan", "--pointer", str(pointer)]))

    def test_a_host_page_keeps_its_section_link_across_a_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"note.md": b"# n\n"})
            pointer = _seed_published_tree(repo, source)
            path = repo / "artefacts" / "manifest.json"
            body = json.loads(path.read_text(encoding="utf-8"))
            section = body["collections"][0]["section"]
            body["site"]["catalogue"]["section_links"] = {
                section: '\n<a class="showcase-link" href="showcase/">3D</a>\n'
            }
            path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            page = (repo / "artefacts" / "index.html").read_text(encoding="utf-8")
            self.assertIn('<a class="showcase-link" href="showcase/">3D</a>', page)
            # Convergent: the link is regenerated, not accumulated.
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            self.assertEqual(1, (repo / "artefacts" / "index.html")
                             .read_text(encoding="utf-8").count("showcase-link"))
```

- [ ] **Step 2: Run it**

Run: `python3 -m unittest tests.test_m4_adoption -v` and again under `/usr/bin/python3`.
Expected: both PASS. If `test_a_published_tree_is_not_rewritten_on_re_adoption` fails with
`M artefacts/...`, one of Tasks 1-4 is incomplete; do not weaken the assertion.

- [ ] **Step 3: Update `SKILL.md`**

In the "Manifest" section, replace the `site` line of the shape block:

```text
  site: {base_url, favicon, catalogue: {mode, page?, section_links?}},
```

and add a paragraph after the one that ends "stored in the manifest":

```markdown
`site.catalogue.section_links` maps a section title to raw HTML appended inside that section's
`<h2>`. It exists for a host page that hangs its own link off a heading the catalogue regenerates.
The value is inserted verbatim, so it carries its own whitespace and is escaped by nobody.
```

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
3. Add any ignore rules the tree relied on. Dotfile directories are the usual gap: `.*` covers them.
4. Run `plan`. Every entry that reports as changed is a rendering difference to explain before you
   sync, not after. `manifest.json` always changes on the first run, because absent `date` values
   are stamped from source modification time.
5. Run `sync`, then `git status`. Anything beyond `artefacts/manifest.json` and
   `artefacts/page-template.html` means the tool renders that file differently from whatever built
   it. Stop and read the diff.
6. Run `plan` again. It must report no change groups. That is the proof the adoption converged.
```

- [ ] **Step 4: Run the whole suite on both interpreters**

```bash
python3 -m unittest discover -s tests -t . 2>&1 | tail -3
/usr/bin/python3 -m unittest discover -s tests -t . 2>&1 | tail -3
git -C /Users/keli/dev/github-kevinlin/kevinlin.github.io status --short
```

Expected: OK on both, 250 tests. The third command prints nothing.

- [ ] **Step 5: Commit**

```bash
git add tests/test_m4_adoption.py SKILL.md
git commit -m "test: prove an existing published tree survives adoption unrewritten"
```

---

### Task 6: the dry run — the gate, against a clone

**Files:**
- Create: `docs/specs/m4-acceptance.md`
- Modify: `docs/specs/design_artefact-sync.md` (corrections M4-a to M4-i)

**Interfaces:**
- Consumes: the whole CLI. Produces no code.

Nothing in this task writes to `/Users/keli/dev/github-kevinlin/kevinlin.github.io`. Everything runs
against a clone in the scratch directory. Run the whole task before Task 7 changes anything real.

Numbers below are what a run against live HEAD `280b17e` produced while this plan was written. A
mismatch is information: record it, do not adjust an assertion to hide it.

- [ ] **Step 1: Re-measure the live tree, read-only**

```bash
SITE=/Users/keli/dev/github-kevinlin/kevinlin.github.io
git -C "$SITE" log --oneline -1
git -C "$SITE" status --short          # must print nothing
python3 - <<'PY'
import json
from pathlib import Path
from artefact_sync import scan
from artefact_sync.manifest import APPROVED_EXTENSIONS
site = Path("/Users/keli/dev/github-kevinlin/kevinlin.github.io")
source = Path.home() / "Downloads" / "Artefacts"
raw = json.loads((site / "artefacts" / "manifest.json").read_text())
print("entries", len(raw["entries"]), "collections", len(raw["collections"]),
      "protected", len(raw["protected_files"]))
inventory = scan.scan_source(source, site)
kept, counts = scan.apply_source_ignores(inventory, tuple(raw["ignored_sources"]))
listed = {e["source"] for e in raw["entries"]}
unlisted = [p.as_posix() for p in kept.approved if p.as_posix() not in listed]
print("approved", len(inventory.approved), "after ignores", len(kept.approved),
      "unlisted", len(unlisted))
for path in unlisted:
    print("   unlisted:", path)
PY
```

Expected: `56 entries`, `31 collections`, `36 protected`, `approved 128`, `after ignores 66`,
`unlisted 10`, and all ten under `.firecrawl/`. If the unlisted list is not exactly the dotfile
directory, read every new name before adding an ignore rule — a genuinely new artefact belongs in
the manifest, not in `ignored_sources`.

- [ ] **Step 2: Clone the site and write the migration prep**

```bash
SCRATCH="$(mktemp -d)"
git clone --quiet --no-hardlinks /Users/keli/dev/github-kevinlin/kevinlin.github.io "$SCRATCH/site"
echo "$SCRATCH"
```

Then, from the skill repository root:

```bash
python3 - "$SCRATCH" <<'PY'
import json, re, sys
from pathlib import Path
scratch = Path(sys.argv[1])
sys.path.insert(0, "/Users/keli/dev/github-kevinlin/kevinlin.github.io/scripts")
import artefacts

# The template, converted for string.Template. Sentinels first so a literal {{word}}
# could never be mistaken for a placeholder; the constant has no "$", so nothing needs
# doubling on the way out.
text = artefacts.MARKDOWN_PAGE_TEMPLATE
assert "$" not in text and "\x00" not in text and "\x01" not in text
text = text.replace("{{", "\x00").replace("}}", "\x01")
text = re.sub(r"\{(\w+)\}", r"$\1", text)
text = text.replace("\x00", "{").replace("\x01", "}")
(scratch / "site/artefacts/page-template.html").write_text(text, encoding="utf-8")

path = scratch / "site/artefacts/manifest.json"
old = json.loads(path.read_text(encoding="utf-8"))
new = {
    "version": old["version"],
    "site": {
        "base_url": "https://kevinlin.github.io/artefacts/",
        "favicon": artefacts.FAVICON_LINK,
        "catalogue": {
            "mode": "inject",
            "page": "index.html",
            "section_links": {
                artefacts.IMAGE_SECTION: f"\n{artefacts.SHOWCASE_LINK}\n            ",
            },
        },
    },
    "protected_files": old["protected_files"],
    "ignored_sources": sorted(old["ignored_sources"] + [".*"]),
    "collections": old["collections"],
    "entries": old["entries"],
}
path.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")

(scratch / "pointer.json").write_text(json.dumps({
    "repo": str(scratch / "site"),
    "source": str(Path.home() / "Downloads" / "Artefacts"),
    "push": "direct",
}, indent=2) + "\n", encoding="utf-8")
print("prep written, uncommitted")
PY
```

The prep stays uncommitted on purpose: the clone's HEAD manifest has no `site` block, so this run is
also the live proof of Task 4.

- [ ] **Step 3: Run the gate**

```bash
python3 -m artefact_sync plan --pointer "$SCRATCH/pointer.json" \
  | grep -E '^[A-Z][A-Z ]*\([0-9]+\)|^  https|^no changes'
```

Expected, exactly:

```
CHANGED (1)
  https://kevinlin.github.io/artefacts/manifest.json
EXCLUDED (161)
WARNINGS (38)
```

No `NEW PUBLIC URLS`, no `WILL START 404-ING`, no `BLOCKED`, and exit 0. `manifest.json` is the only
change because absent `date` values get stamped; every published page and image is already correct.

The 38 warnings are 30 `external` and 8 `secret`. Read all 8 secret rows before continuing. Five sit
in Markdown sources and three in `everything-llm/swe_bench_pro_by_lab.html`, and every one is the
40-hex rule firing on a git SHA or a benchmark id. Confirm that, in the record, by name.

Then apply and check the diff surface:

```bash
python3 -m artefact_sync sync --pointer "$SCRATCH/pointer.json" --yes > /dev/null
git -C "$SCRATCH/site" status --short
python3 -m artefact_sync plan --pointer "$SCRATCH/pointer.json" \
  | grep -E '^[A-Z][A-Z ]*\([0-9]+\)|^no changes'
python3 -m artefact_sync validate --pointer "$SCRATCH/pointer.json" > /dev/null; echo "validate=$?"
```

Expected:

```
 M artefacts/manifest.json
?? artefacts/page-template.html
EXCLUDED (161)
WARNINGS (38)
validate=0
```

The second `plan` shows no change group at all. That is convergence, and it is the gate.

- [ ] **Step 4: Prove the manifest diff is only what was intended**

```bash
git -C "$SCRATCH/site" diff -U0 -- artefacts/manifest.json | grep -c '^+.*"date"'
git -C "$SCRATCH/site" diff -U0 -- artefacts/manifest.json \
  | grep -E '^[+-]' | grep -vE '"date"|"replacements"' | grep -vE '^(\+\+\+|---)'
```

Expected: `56` dates added, and the remaining lines are only the `site` block, `".*"` in
`ignored_sources`, `catalogue.section_links`, and one title where `—` becomes a literal em
dash — the skill emits `ensure_ascii=False`, the prior art did not. Any other line is a defect: stop
and diagnose it.

- [ ] **Step 5: Prove no published byte moved**

```bash
git -C "$SCRATCH/site" diff --name-only HEAD -- artefacts
git -C "$SCRATCH/site" ls-files --others --exclude-standard artefacts
```

Expected: `artefacts/manifest.json` and nothing else from the first command;
`artefacts/page-template.html` and nothing else from the second. That statement covers all 56 entry
destinations, all 36 protected files and `artefacts/index.html`.

- [ ] **Step 6: Check the live working tree's one known difference**

The live working tree is not identical to its own committed blobs: `core.autocrlf = input` is set in
`~/.gitconfig`, and one source (`agent-harness/20260713_loop-engineering-raw.md`) has CRLF endings,
so git stored the page it renders to with 16 CRs removed. Confirm that is still the only such file:

```bash
SITE=/Users/keli/dev/github-kevinlin/kevinlin.github.io
python3 - <<'PY'
import subprocess
from pathlib import Path
site = Path("/Users/keli/dev/github-kevinlin/kevinlin.github.io")
for path in sorted((site / "artefacts").rglob("*")):
    if not path.is_file():
        continue
    relative = path.relative_to(site).as_posix()
    result = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=site, capture_output=True)
    if result.returncode != 0:
        print("untracked:", relative)
    elif result.stdout != path.read_bytes():
        print("differs from blob:", relative,
              f"working={path.read_bytes().count(b'\\r')}CR blob={result.stdout.count(b'\\r')}CR")
PY
```

Expected: two untracked `.DS_Store` files, and
`artefacts/agent-harness/20260713-loop-engineering-raw/index.html` with `working=16CR blob=0CR`.
Consequence for Task 7: `plan` against the live working tree reports that one entry as CHANGED where
the clone reported nothing, `sync` rewrites it to LF, and the commit contains no change for that
path because git had already normalised it. Task 1 is what makes this converge instead of recurring
on every run forever.

- [ ] **Step 7: Write the acceptance record**

Create `docs/specs/m4-acceptance.md`, following the shape of
[m2-acceptance.md](m2-acceptance.md): a numbered table with `#`, `Command`, `Expected`, `Result`,
one row per step above, then a "What the run found" section and a "Result" line. Cover Steps 1-6 as
rows 1-6 and leave rows 7 onwards for Task 8, so the whole gate lives in one document. Record the
actual figures, not the predicted ones.

- [ ] **Step 8: Apply the corrections to the design**

In `docs/specs/design_artefact-sync.md`, add M4-a to M4-i from this plan's "Corrections to the
design this plan applies" table to the "Changes to the requirement" table, and make these edits in
place:

- "Rendering": state the invariant as text-exact after UTF-8 decode, line-ending normalisation and
  trailing-newline normalisation, and correct "55 doubled-brace escapes" to 36 pairs.
- "Rendering": add `section_links` to the `site.catalogue` shape and note that inject mode reuses the
  fragment markup, so the host page's CSS is what pins the class names.
- "Schemas": add `section_links?` to the `site` line.
- "Release ladder" and "Testing": 56 entries, not 57.
- "Release ladder": the atlas rehomes to a documented manual step, per M4-h.

- [ ] **Step 9: Clean up and commit**

```bash
rm -rf "$SCRATCH"
git -C /Users/keli/dev/github-kevinlin/kevinlin.github.io status --short
git add docs/specs/m4-acceptance.md docs/specs/design_artefact-sync.md
git commit -m "docs: record the M4 dry run and the design corrections it forced"
```

Expected: the status command prints nothing.

---

### Task 7: the site side — rehome the atlas, retire the prior art

**Files (all in `/Users/keli/dev/github-kevinlin/kevinlin.github.io`, on a branch):**
- Delete: `scripts/artefacts.py`, `tests/test_artefacts.py`, `scripts/__pycache__`,
  `tests/__pycache__`
- Modify: `.github/workflows/validate-artefacts.yml`, `CLAUDE.md`, `AGENTS.md`, `README.md`
- Keep untouched: `scripts/build_showcase_atlas.py`

**Interfaces:**
- Consumes nothing from the skill repository. Produces the site-side state Task 8 publishes into.

This is the first task that writes to the live repository. It writes no file under `artefacts/`, so
Task 8's `publish` preflight — which refuses any change outside `artefacts/` — forces this task to be
merged before Task 8 runs. Do it as a pull request, which is also how this repository has taken every
recent change.

- [ ] **Step 1: Branch**

```bash
SITE=/Users/keli/dev/github-kevinlin/kevinlin.github.io
git -C "$SITE" status --short          # must print nothing
git -C "$SITE" switch -c retire-artefacts-script
```

- [ ] **Step 2: Delete the prior art**

```bash
git -C "$SITE" rm -q scripts/artefacts.py tests/test_artefacts.py
rm -rf "$SITE/scripts/__pycache__" "$SITE/tests/__pycache__"
```

Two copies of the same logic running against one live tree is the drift the design's D1 exists to
prevent. `scripts/build_showcase_atlas.py` stays: it is site-specific, needs `ffmpeg`, and was never
ported.

- [ ] **Step 3: Rewrite the workflow**

Replace `.github/workflows/validate-artefacts.yml` entirely:

```yaml
name: Validate artefacts

on:
  pull_request:
    paths:
      - ".github/workflows/validate-artefacts.yml"
      - "artefacts/**"

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Check the manifest parses and every declared file is present
        run: |
          python3 - <<'PY'
          import json, sys
          from pathlib import Path
          root = Path("artefacts")
          manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
          declared = [entry["destination"] for entry in manifest["entries"]]
          declared += manifest["protected_files"]
          missing = [name for name in declared if not (root / name).is_file()]
          duplicates = sorted({name for name in declared if declared.count(name) > 1})
          for name in missing:
              print(f"missing: artefacts/{name}")
          for name in duplicates:
              print(f"declared twice: artefacts/{name}")
          sys.exit(1 if missing or duplicates else 0)
          PY
```

`artefact-sync validate` is not run here on purpose: the skill is not installed on the runner, and
installing it would put the tool's own version drift into the site's CI. What CI can still catch
without the tool is a manifest that names a file the tree does not have — which is the failure a
half-applied sync leaves behind.

- [ ] **Step 4: Rehome the atlas into the documentation**

In both `CLAUDE.md` and `AGENTS.md`, replace the numbered item 2 and the command block that follows
it. Find the paragraph beginning "**The artefact publishing pipeline** — `scripts/artefacts.py`" and
the fenced block containing `python3 scripts/artefacts.py plan`, and put this in their place:

````markdown
2. **The artefact publishing pipeline** — the `artefact-sync` skill at
   `~/.claude/skills/artefact-sync/`, a stdlib-only Python CLI that syncs approved files from
   `~/Downloads/Artefacts` into the public `artefacts/` tree, regenerates the catalogue between the
   `ARTEFACTS:START` / `ARTEFACTS:END` markers in `artefacts/index.html`, and publishes. The tool
   lives outside this repository; `artefacts/manifest.json` and `artefacts/page-template.html` live
   in it.

```bash
python3 -m artefact_sync plan        # read-only: what would change, and every URL
python3 -m artefact_sync sync        # apply locally, commit nothing
python3 -m artefact_sync validate    # offline checks over the published tree
python3 -m artefact_sync publish     # apply, commit, push, wait for Pages, verify every URL
```

After any sync that **adds or removes a published image**, repack the 3D showcase atlas by hand and
commit the result:

```bash
python3 scripts/build_showcase_atlas.py
git status --short artefacts/showcase/
```

Nothing runs this for you. It needs `ffmpeg` and `ffprobe` on `PATH`, and its JPEG output is
encoder-dependent, so a CI staleness check would fail on byte differences rather than on real
staleness. Text-only and manifest-only syncs leave the atlas correct: panel order follows the
catalogue's section, collection and entry order, which a text change does not move.
````

In `README.md`, replace `python3 scripts/artefacts.py plan` with `python3 -m artefact_sync plan` and
`python3 scripts/artefacts.py publish` with `python3 -m artefact_sync publish`.

- [ ] **Step 5: Check nothing else references the deleted script**

```bash
grep -rn 'scripts/artefacts\.py\|tests/test_artefacts\.py' "$SITE" \
  --include='*.md' --include='*.yml' --include='*.html' --include='*.py' \
  | grep -v '^.*/docs/specs/'
```

Expected: no output. Matches under `docs/specs/` are that repository's copies of these
specifications, which describe the prior art on purpose; leave them.

- [ ] **Step 6: Commit, push, and merge**

```bash
git -C "$SITE" add -A
git -C "$SITE" commit -m "chore: retire scripts/artefacts.py for the artefact-sync skill"
git -C "$SITE" push -u origin retire-artefacts-script
gh pr create --repo kevinlin/kevinlin.github.io --fill
```

Wait for the workflow to pass, merge the pull request, then:

```bash
git -C "$SITE" switch main
git -C "$SITE" pull --ff-only origin main
git -C "$SITE" status --short          # must print nothing
```

Do not run Task 8 until this prints nothing on `main`. `publish` refuses a working tree with changes
outside `artefacts/`, and it refuses a `main` that has diverged from `origin/main`.

---

### Task 8: the live cutover

**Files:**
- Modify (in the site repository): `artefacts/manifest.json`, add `artefacts/page-template.html`
- Modify: `docs/specs/m4-acceptance.md` (rows 7 onwards, and the result)
- Modify: `docs/specs/plan_artefact-sync-m4.md` (status line, deviations)

**Interfaces:**
- Consumes: everything. Produces the release.

This is the irreversible one. 56 live URLs are at stake, and search engines have all of them cached.
Task 6 is the rehearsal; if Task 6 did not produce exactly its expected output, do not run this task.

- [ ] **Step 1: Install the skill and point it at the site**

```bash
git -C /Users/keli/dev/ai-practitioner/artefact-sync status --short   # must print nothing
ln -s /Users/keli/dev/ai-practitioner/artefact-sync ~/.claude/skills/artefact-sync
ls ~/.claude/skills/artefact-sync/SKILL.md
```

A symlink rather than a clone, so the release gate tests the code that is about to be tagged rather
than a copy of it. Distribution by `git clone` is unchanged for everyone else.

Then write the prep into the live repository, using the same script as Task 6 Step 2 with the clone
path replaced by `/Users/keli/dev/github-kevinlin/kevinlin.github.io` and no pointer file — the
pointer goes to its real home:

```bash
cd /Users/keli/dev/ai-practitioner/artefact-sync
python3 -m artefact_sync init \
  --repo /Users/keli/dev/github-kevinlin/kevinlin.github.io \
  --source ~/Downloads/Artefacts
```

`init` is safe here: it creates nothing that exists. `artefacts/manifest.json` and
`artefacts/vendor/marked.min.js` are already present, so it skips both, writes the pointer, and
fetches `site.base_url` once. Then run the Task 6 Step 2 prep script against the live path.

Expected from `init`: `pointer written to ~/.config/artefact-sync/config.json`, `seeded .../artefacts`,
and `verified https://kevinlin.github.io/artefacts/`. A 404 there means `base_url` is wrong: fix it
before going further.

- [ ] **Step 2: Plan against the live tree, then publish on a branch**

```bash
python3 -m artefact_sync plan | grep -E '^[A-Z][A-Z ]*\([0-9]+\)|^  https'
```

Expected: `CHANGED (2)` — `manifest.json` and
`https://kevinlin.github.io/artefacts/agent-harness/20260713-loop-engineering-raw/`, the second being
the CRLF page from Task 6 Step 6. Nothing else, and no `NEW PUBLIC URLS`, `WILL START 404-ING` or
`BLOCKED`.

Then set branch mode and publish, so the change lands as a reviewable diff rather than straight onto
`main`:

```bash
python3 - <<'PY'
import json
from pathlib import Path
path = Path.home() / ".config" / "artefact-sync" / "config.json"
body = json.loads(path.read_text(encoding="utf-8"))
body["push"] = "branch"
path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
print(body)
PY
python3 -m artefact_sync publish
```

Expected: the irreversibility confirmation lists no new URLs, the branch
`artefact-sync/<timestamp>` is pushed, a `compare/main...` URL is printed, and no build wait or URL
verification runs. `origin/main` has not moved.

- [ ] **Step 3: Review the diff by eye, then merge**

Open the printed compare URL and check the whole diff against Task 6:

- `artefacts/manifest.json`: 56 `date` fields, the `site` block, `".*"`, `section_links`, one em dash.
- `artefacts/page-template.html`: added.
- `artefacts/agent-harness/20260713-loop-engineering-raw/index.html`: **absent from the diff**. Git
  had already normalised its CRs, so the LF page `sync` wrote matches the committed blob.
- Nothing else. If any other published file appears, close the pull request without merging and go
  back to Task 6.

Merge it, then return to direct mode on an up-to-date `main`:

```bash
SITE=/Users/keli/dev/github-kevinlin/kevinlin.github.io
git -C "$SITE" switch main
git -C "$SITE" pull --ff-only origin main
python3 - <<'PY'
import json
from pathlib import Path
path = Path.home() / ".config" / "artefact-sync" / "config.json"
body = json.loads(path.read_text(encoding="utf-8"))
body["push"] = "direct"
path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
PY
```

- [ ] **Step 4: Verify every published URL**

```bash
time python3 -m artefact_sync publish
```

Expected: `no changes.` then `nothing to publish; 94 published URLs verified.` — the base URL,
`index.html`, 56 entries and 36 protected files. No new commit. Record the wall-clock time: 94
sequential fetches is roughly fifteen times M2's six, and a run past a few minutes is worth knowing
about before anyone adds another hundred entries.

- [ ] **Step 5: Check the site in a browser**

Open `https://kevinlin.github.io/artefacts/` and confirm:

- The catalogue looks exactly as it did. Card order, "Updated" dates, and the "Walk the image
  artefacts in 3D" link on the Image collections heading are all present.
- That link opens `showcase/` and the 3D gallery still renders — the atlas was not touched, and this
  is the check that proves the `section_links` hook did its job.
- One Markdown page renders through `marked.js` with no console errors. Use
  `agent-harness/20260713-loop-engineering-raw/`, the CRLF one, and confirm its Cyrillic block still
  reads correctly.
- Two images and the PDF-free byte-copy formats still load.

- [ ] **Step 6: Prove nothing published moved, over the whole cutover**

```bash
SITE=/Users/keli/dev/github-kevinlin/kevinlin.github.io
git -C "$SITE" diff --stat 280b17e..HEAD -- artefacts
```

Expected: `artefacts/manifest.json` and `artefacts/page-template.html`, and nothing else. Replace
`280b17e` with whatever HEAD was before Task 7 if the site moved on. This one command is the release
gate's whole claim, and it should be the last line of the acceptance record.

- [ ] **Step 7: Finish the record and commit**

Fill in rows 7 onwards of `docs/specs/m4-acceptance.md` from Steps 1-6, write its "What the run
found" and "Result" sections, set this plan's status line, and fill in "Deviations from this plan"
with every place the plan was wrong, corrected test counts included. Then:

```bash
cd /Users/keli/dev/ai-practitioner/artefact-sync
git add docs/specs/m4-acceptance.md docs/specs/plan_artefact-sync-m4.md
git commit -m "docs: record the M4 release gate against 56 live URLs"
```

---

## Critical Files — Summary

| Path | M4's change |
|---|---|
| `artefact_sync/render.py` | `normalise_source_text`, `BLOCK_START` gains the prior art's id and newline, `$vendor` loses the baked-in prefix |
| `artefact_sync/apply.py` | Round-trip verification normalises the source the same way the renderer does |
| `artefact_sync/catalogue.py` | Prior-art markup, `section_slug`, cards by date and entries by order, `section_links` |
| `artefact_sync/config.py` | `Site.section_links`, read and re-emitted |
| `artefact_sync/manifest.py` | `head_manifest` tolerates a HEAD manifest predating the `site` block |
| `artefact_sync/assets/page-template.html` | `src="$prefix$vendor"`, `markdown-source`, leading-newline strip |
| `artefact_sync/assets/catalogue-template.html` | CSS matches the new fragment markup |
| `SKILL.md` | `section_links`, and "Adopting an existing artefacts tree" |
| `docs/specs/m4-acceptance.md` | The dry run and the live cutover |
| `kevinlin.github.io` | `scripts/artefacts.py` and its tests deleted, workflow rewritten, atlas rehomed into the docs, `site` block and template added |

---

## Warnings

- **Task 8 is irreversible.** 56 URLs are cached by search engines. Task 6 is the rehearsal that
  makes Task 8 safe, so run it first.
- **Do not "fix" a published page to make a diff go away.** Every one of the four code fixes exists
  because the tool was rendering something differently from what was published. If a fifth
  difference appears, find out which side is wrong before changing either.
- **Do not add an `ignored_sources` rule to silence a blocked file** without reading the file. The
  `.*` rule is right because the prior art skipped dotfile directories all along. A genuinely new
  artefact belongs in the manifest.
- **The 40-hex secret rule warns on git SHAs.** Eight warnings on the live tree are all false
  positives. Read them anyway; that is what a warning is for.
- **`section_links` HTML is inserted verbatim.** It is the user's own manifest, at the same trust
  level as `favicon`, and it is escaped by nobody.
- **The atlas is nobody's automatic job after M4.** The migration itself changes zero images, so
  nothing goes stale on day one. The next published image needs a hand-run.

---

## Self-Review

**Spec coverage.** Walked the design's M4 paragraph and every section the migration touches.

| Spec item | Task |
|---|---|
| "Copy the site's existing template verbatim into `page-template.html`" | 6 Step 2, with the conversion proven by the 9 Markdown pages coming out byte-identical |
| "Seed `date` from current mtimes" | Already built: `plan._stamp_missing_dates` runs inside `create_sync_plan`. Verified in 6 Step 4 as 56 date lines |
| "Install the skill" | 8 Step 1 |
| "Run `plan` against the live tree, and require zero changes" | 6 Step 3 (clone: one change, `manifest.json`), 8 Step 2 (live tree: two, the second explained by `core.autocrlf`). Restated as the measurable claim in 8 Step 6 |
| "An empty plan across the real entries proves the extraction preserved behaviour" | 6 Step 5 and 8 Step 6 both prove it as a git diff over the published tree, which is stronger: it covers protected files and the catalogue, which no plan group reports |
| "Drift in escaping, catalogue rendering, ordering or transformation all show up as a non-empty plan" | Found four such drifts. Escaping: Task 2. Catalogue rendering and ordering: Task 3. Transformation: Task 1 |
| "Migration also has to rehome the atlas" | 7 Step 4, as a documented manual step (M4-h) |
| "`kevinlin.github.io` keeps its own copy ... the two will drift" — reversed by D1 | 7 Step 2 deletes the copy |
| D5: `init` writes `vendor/marked.min.js` and `page-template.html` into the repo | 8 Step 1. Both already exist or are written by the prep, and `init` skips what is present |
| Invariant 1: an existing entry is never re-titled or re-slugged | Enforced throughout, and Task 4 is what keeps it enforced during adoption rather than silently disabled |
| Invariant 2: `destination` is frozen once published | Same. 6 Step 5 proves no destination moved |
| Invariant 4: orphans are never deleted | 6 Step 3: zero orphan warnings, because every file in the published tree is an entry, a protected file, a reserved name, or an untracked `.DS_Store` that `scan_published_tree` skips |
| "Post-push URL verification is the only proof a publish worked" | 8 Step 4, 94 URLs |
| Testing ledger: "Publish: rewrite all ... unit tests cannot close the publish gap" | 8 is that gap's second and last closure, after M2 |

**Deliberately not done, and why.**

- **No second page template and no catalogue templating engine.** The fragment's markup is now the
  prior art's, and a host page adapts by styling those class names. A fragment template would need
  loops over sections, cards and items, which `string.Template` cannot express, so it would mean
  shipping a small templating engine to serve one site.
- **No CI staleness check for the atlas.** `build_showcase_atlas.py` shells out to `ffmpeg`, whose
  JPEG output differs between builds, so the check would fail on encoder differences and be
  disabled within a week. M4-h.
- **`artefact-sync validate` is not run in the site's CI.** The skill is not installed on the
  runner. The workflow keeps the one check that needs no tool: every declared file exists.
- **The 10 collections with no entries stay in the manifest.** They render nothing and validate
  cleanly. Deleting somebody's placeholder collections is not a migration's business.
- **`ensure_ascii=False` stays.** It changes one manifest line on the cutover and makes every future
  manifest readable. `manifest.json` is not a page anyone renders.
- **No `.gitattributes` in the site repository.** Setting `artefacts/** -text` would also stop git
  normalising and would keep bytes exact, but it fixes one repository and leaves the tool broken for
  the next adopter whose git normalises. Task 1 fixes the tool.
- **No version bump.** The design accepts that `manifest.version` has no source of truth. M4 adds
  one optional key inside `site.catalogue` and one optional field nobody has to set, so an old
  manifest still loads.

**Type consistency.** `normalise_source_text(source_bytes: bytes, label: str) -> str` has one
signature across its definition in `render.py` and its three callers (`render_markdown_page`,
`transform_html`, `apply.verify_markdown_round_trip`). `render_catalogue(manifest, site)` keeps the
signature `catalogue.render_standalone_catalogue`, `plan.create_sync_plan` and `validate` already
call. `section_slug(value: str) -> str` is defined and called only inside `catalogue.py`.
`Site.section_links` is a `dict` with a `field(default_factory=dict)`, read in `site_from_dict`,
written in `site_to_dict`, and consumed in `render_catalogue`; every positional four-argument
`Site(...)` construction in `selfcheck.py` and the tests keeps working. `catalogue.entry_sort_key`
and `catalogue._invert` are deleted, and `tests/test_catalogue.py::SortTests` — their only caller —
is deleted with them. `head_manifest(repo_root) -> Manifest | None` is unchanged in signature, so
`cli._command_state` and every publish path are untouched. `BLOCK_START` and `BLOCK_END` keep their
names; only `BLOCK_START`'s value moves.

**Predicted counts.** 227 at the start, then 231, 232, 244, 246, 250. Every one is a prediction; see
the last global constraint. Tasks 6, 7 and 8 add no tests.

---

## Deviations from this plan

Recorded because the plan was written before the code existed, and a plan that hides where it was
wrong is worth less on the next milestone.

_To be filled in during implementation._

## After M4

M4 is the last milestone in the design's ladder. What the gate leaves open, in the order it will
matter:

- **`manifest.version` still has no source of truth.** M4 added `site.catalogue.section_links` and
  changed `BLOCK_START`, and neither carries a migration signal. The next adopter of a pre-M4 tree
  gets no warning that the block id moved; they will find out from a non-empty plan, which is how
  M4 found everything.
- **Nothing verifies that the bytes GitHub serves equal the bytes pushed.** `publish` checks status
  codes. M2 hand-compared sha256 for two files, and M4 found a real case where git changed the bytes
  between apply and publish. A byte comparison in `publish` for the text formats is the obvious next
  guard.
- **The atlas is a manual step.** If a published image is added and the atlas is not repacked, the
  3D showcase shows a stale panel set with no warning anywhere.
