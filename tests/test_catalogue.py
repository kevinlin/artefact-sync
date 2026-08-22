from __future__ import annotations

import unittest
from pathlib import PurePosixPath

from artefact_sync import catalogue
from artefact_sync.config import site_from_dict
from artefact_sync.manifest import Collection, Entry, Manifest

SITE = site_from_dict({"base_url": "https://x.example/artefacts/"})


def build(entries) -> Manifest:
    return Manifest(
        version=1, site=SITE, protected_files=(), ignored_sources=(),
        collections=(Collection(id="c", title="C", description=None, section="S",
                                section_order=10, order=10),),
        entries=tuple(entries),
    )


def entry(**overrides) -> Entry:
    body = dict(id="e", source=PurePosixPath("a.md"),
                destination=PurePosixPath("a/index.html"), title="A", collection="c",
                order=10, replacements={})
    body.update(overrides)
    return Entry(**body)


class InjectionTests(unittest.TestCase):
    def test_replaces_only_between_the_markers(self) -> None:
        document = f"before\n{catalogue.CATALOGUE_START}\nold\n{catalogue.CATALOGUE_END}\nafter\n"
        out = catalogue.replace_generated_catalogue(document, "new")
        self.assertEqual(
            f"before\n{catalogue.CATALOGUE_START}\nnew\n{catalogue.CATALOGUE_END}\nafter\n", out
        )

    def test_a_missing_marker_pair_is_an_error(self) -> None:
        from artefact_sync.errors import ValidationError

        with self.assertRaises(ValidationError):
            catalogue.replace_generated_catalogue("no markers here\n", "new")

    def test_duplicate_markers_are_an_error(self) -> None:
        from artefact_sync.errors import ValidationError

        document = f"{catalogue.CATALOGUE_START}{catalogue.CATALOGUE_START}{catalogue.CATALOGUE_END}"
        with self.assertRaises(ValidationError):
            catalogue.replace_generated_catalogue(document, "new")


class StandaloneTests(unittest.TestCase):
    def test_generates_a_whole_page_with_markers_for_later_injection(self) -> None:
        page = catalogue.render_standalone_catalogue(build([entry()]), SITE).decode("utf-8")
        self.assertIn("<!DOCTYPE html>", page)
        self.assertIn(catalogue.CATALOGUE_START, page)
        self.assertIn(catalogue.CATALOGUE_END, page)

    def test_a_generated_page_can_be_re_injected_without_drift(self) -> None:
        manifest = build([entry()])
        first = catalogue.render_standalone_catalogue(manifest, SITE).decode("utf-8")
        again = catalogue.replace_generated_catalogue(
            first, catalogue.render_catalogue(manifest, SITE)
        )
        self.assertEqual(first, again)


class SortTests(unittest.TestCase):
    def test_dated_entries_sort_newest_first(self) -> None:
        old = entry(id="old", destination=PurePosixPath("o/index.html"), date="2026-01-01")
        new = entry(id="new", destination=PurePosixPath("n/index.html"), date="2026-06-01")
        ordered = sorted([old, new], key=catalogue.entry_sort_key)
        self.assertEqual(["new", "old"], [e.id for e in ordered])

    def test_undated_entries_fall_back_to_order(self) -> None:
        first = entry(id="first", destination=PurePosixPath("f/index.html"), order=10)
        second = entry(id="second", destination=PurePosixPath("s/index.html"), order=20)
        ordered = sorted([second, first], key=catalogue.entry_sort_key)
        self.assertEqual(["first", "second"], [e.id for e in ordered])

    def test_titles_are_escaped(self) -> None:
        fragment = catalogue.render_catalogue(build([entry(title="a <b> & c")]), SITE)
        self.assertIn("a &lt;b&gt; &amp; c", fragment)
        self.assertNotIn("<b>", fragment)
