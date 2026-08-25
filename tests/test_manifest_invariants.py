from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath

import manifest as m
from errors import ValidationError
from tests.helpers import make_repo


def entry(**overrides) -> m.Entry:
    body = dict(
        id="e", source=PurePosixPath("a.png"), destination=PurePosixPath("a.png"),
        title="A", collection="c", order=10, replacements={},
    )
    body.update(overrides)
    return m.Entry(**body)


def manifest(entries) -> m.Manifest:
    from config import site_from_dict

    return m.Manifest(
        version=1,
        site=site_from_dict({"base_url": "https://x.example/artefacts/"}),
        protected_files=(),
        ignored_sources=(),
        collections=(m.Collection(id="c", title="C", description=None, section="S",
                                  section_order=10, order=10),),
        entries=tuple(entries),
    )


class InvariantTests(unittest.TestCase):
    def test_a_changed_destination_is_rejected_and_names_the_url(self) -> None:
        head = manifest([entry()])
        current = manifest([entry(destination=PurePosixPath("moved.png"))])
        with self.assertRaises(ValidationError) as caught:
            m.check_published_invariants(current, head)
        self.assertIn("a.png", str(caught.exception))

    def test_a_changed_title_is_rejected(self) -> None:
        head = manifest([entry()])
        current = manifest([entry(title="Renamed")])
        with self.assertRaises(ValidationError):
            m.check_published_invariants(current, head)

    def test_a_changed_source_is_allowed_when_the_destination_holds(self) -> None:
        head = manifest([entry()])
        current = manifest([entry(source=PurePosixPath("renamed.png"))])
        m.check_published_invariants(current, head)  # must not raise

    def test_a_new_entry_is_allowed(self) -> None:
        head = manifest([entry()])
        current = manifest([entry(), entry(id="e2", source=PurePosixPath("b.png"),
                                          destination=PurePosixPath("b.png"))])
        m.check_published_invariants(current, head)

    def test_a_removed_entry_is_allowed(self) -> None:
        m.check_published_invariants(manifest([]), manifest([entry()]))

    def test_no_head_manifest_means_nothing_to_protect(self) -> None:
        m.check_published_invariants(manifest([entry()]), None)


class HeadManifestTests(unittest.TestCase):
    def test_returns_none_when_the_repo_has_no_manifest_in_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp), {"README.md": b"x\n"})
            self.assertIsNone(m.head_manifest(repo))


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
