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

    def test_the_vendor_path_is_relative_to_the_destination_depth(self) -> None:
        page = render.render_markdown_page(
            ENTRY, b"# x\n", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        ).decode("utf-8")
        self.assertIn('<script src="../../vendor/marked.min.js"></script>', page)

    def test_the_renderer_reads_the_embedded_source_block_id(self) -> None:
        page = render.render_markdown_page(
            ENTRY, b"# x\n", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        ).decode("utf-8")
        self.assertIn('id="artefact-source"', page)
        self.assertIn("getElementById('artefact-source')", page)

    def test_the_browser_does_not_strip_a_leading_source_newline(self) -> None:
        raw = Path("artefact_sync/assets/page-template.html").read_text(encoding="utf-8")
        self.assertNotIn(r".replace(/^\n/, '')", raw)
