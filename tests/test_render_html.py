from __future__ import annotations

import unittest
from pathlib import PurePosixPath

import render
from config import site_from_dict
from manifest import Entry

SITE = site_from_dict({"base_url": "https://x.example/artefacts/"})


def entry(**overrides) -> Entry:
    body = dict(
        id="e", source=PurePosixPath("a/p.html"), destination=PurePosixPath("a/p/index.html"),
        title="P", collection="c", order=10, replacements={},
    )
    body.update(overrides)
    return Entry(**body)


class TransformTests(unittest.TestCase):
    def test_applies_replacements_in_order(self) -> None:
        source = b"<html><head></head><body>AAA</body></html>"
        out = render.transform_html(source, entry(replacements={"AAA": "BBB", "BBB": "CCC"}), SITE)
        self.assertIn(b"CCC", out)

    def test_a_replacement_that_never_matches_is_an_error(self) -> None:
        from errors import TransformationError

        with self.assertRaises(TransformationError):
            render.transform_html(b"<html></html>", entry(replacements={"absent": "x"}), SITE)

    def test_crlf_line_endings_normalise_to_lf(self) -> None:
        out = render.transform_html(b"<html><head></head><body>x</body></html>\r\n", entry(), SITE)
        self.assertNotIn(b"\r", out)
        self.assertTrue(out.endswith(b"\n"))

    def test_inserts_the_site_favicon_when_the_page_has_none(self) -> None:
        out = render.transform_html(b"<html><head></head><body></body></html>", entry(), SITE)
        self.assertIn(SITE.favicon.encode("utf-8"), out)

    def test_leaves_an_existing_favicon_alone(self) -> None:
        source = b'<html><head><link rel="icon" href="own.png"></head><body></body></html>'
        out = render.transform_html(source, entry(), SITE)
        self.assertIn(b"own.png", out)
        self.assertEqual(1, out.count(b'rel="icon"'))

    def test_strips_trailing_whitespace(self) -> None:
        out = render.transform_html(b"<html>   \n<body></body></html>\n", entry(), SITE)
        self.assertNotIn(b"   \n", out)


class ExternalReferenceTests(unittest.TestCase):
    def test_reports_every_off_site_reference_with_its_line(self) -> None:
        text = (
            "<html>\n"
            '<script src="https://cdnjs.cloudflare.com/x.js"></script>\n'
            '<script src="https://unpkg.com/y.js"></script>\n'
            '<img src="local.png">\n'
            "</html>\n"
        )
        found = render.external_references(text)
        self.assertEqual(
            [(2, "https://cdnjs.cloudflare.com/x.js"), (3, "https://unpkg.com/y.js")], list(found)
        )

    def test_a_page_with_only_local_references_reports_nothing(self) -> None:
        self.assertEqual((), render.external_references('<img src="../a/b.png">\n'))

    def test_protocol_relative_urls_count_as_external(self) -> None:
        self.assertEqual(1, len(render.external_references('<script src="//cdn.example/x.js">\n')))

    def test_an_inline_data_url_is_not_off_site(self) -> None:
        self.assertEqual((), render.external_references('<link href="data:,">\n'))

    def test_a_plain_hyperlink_is_not_a_fetched_asset(self) -> None:
        self.assertEqual((), render.external_references('<a href="https://example.com/x">x</a>\n'))

    def test_a_stylesheet_link_is_a_fetched_asset(self) -> None:
        text = '<link rel="stylesheet" href="https://fonts.example/css2?family=X">\n'
        self.assertEqual(1, len(render.external_references(text)))
