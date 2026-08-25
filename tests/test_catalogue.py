from __future__ import annotations

import unittest
from pathlib import PurePosixPath

from artefact_sync import catalogue
from artefact_sync.config import site_from_dict
from artefact_sync.manifest import Collection, Entry, Manifest

SITE = site_from_dict({"base_url": "https://x.example/artefacts/"})


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
