from __future__ import annotations

import string
import unittest
from pathlib import Path, PurePosixPath

from artefact_sync import render
from artefact_sync.config import site_from_dict
from artefact_sync.errors import TransformationError
from artefact_sync.manifest import Entry

SITE = site_from_dict({"base_url": "https://x.example/artefacts/"})
TEMPLATE = string.Template(
    Path("artefact_sync/assets/page-template.html").read_text(encoding="utf-8")
)
ENTRY = Entry(
    id="e", source=PurePosixPath("a/n.md"), destination=PurePosixPath("a/n/index.html"),
    title="A note", collection="c", order=10, replacements={},
)


class RoundTripTests(unittest.TestCase):
    def test_a_leading_blank_line_survives_embedding_and_extraction(self) -> None:
        body = "\n# Title\n"
        page = render.render_markdown_page(
            ENTRY, body.encode("utf-8"), PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        )
        self.assertEqual(body, render.extract_markdown(page.decode("utf-8")))

    def test_markdown_survives_embedding_and_extraction(self) -> None:
        body = "# Title\n\nText with `code` and trailing spaces   \n"
        page = render.render_markdown_page(
            ENTRY, body.encode("utf-8"), PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        )
        self.assertEqual(body, render.extract_markdown(page.decode("utf-8")))

    def test_a_closing_script_tag_in_the_source_survives(self) -> None:
        body = "Embedding </script> and <!-- a comment --> inline.\n"
        page = render.render_markdown_page(
            ENTRY, body.encode("utf-8"), PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        )
        self.assertNotIn("</script>\n</script>", page.decode("utf-8"))
        self.assertEqual(body, render.extract_markdown(page.decode("utf-8")))

    def test_a_source_without_a_final_newline_gains_one(self) -> None:
        # The prior art normalises this and has no test for it (artefacts.py:817-850).
        page = render.render_markdown_page(
            ENTRY, b"no trailing newline", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        )
        self.assertEqual("no trailing newline\n", render.extract_markdown(page.decode("utf-8")))

    def test_rejects_a_source_that_is_not_utf8(self) -> None:
        with self.assertRaises(TransformationError):
            render.render_markdown_page(
                ENTRY, b"\xff\xfe", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
            )

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

    def test_rendering_is_deterministic(self) -> None:
        args = (ENTRY, b"# x\n", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE)
        self.assertEqual(
            render.render_markdown_page(*args), render.render_markdown_page(*args)
        )


class TemplateTests(unittest.TestCase):
    def test_the_shipped_template_needs_no_brace_escaping(self) -> None:
        raw = Path("artefact_sync/assets/page-template.html").read_text(encoding="utf-8")
        self.assertNotIn("{{", raw)
        self.assertNotIn("}}", raw)

    def test_the_shipped_template_carries_no_branding(self) -> None:
        raw = Path("artefact_sync/assets/page-template.html").read_text(encoding="utf-8").lower()
        for token in ("kevin", "kevinlin", "github.io"):
            self.assertNotIn(token, raw)

    def test_every_placeholder_is_substituted(self) -> None:
        page = render.render_markdown_page(
            ENTRY, b"# x\n", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        ).decode("utf-8")
        self.assertNotIn("$title", page)
        self.assertNotIn("$vendor", page)
        self.assertIn("A note", page)

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
