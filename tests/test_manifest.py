from __future__ import annotations

import json
import unittest
from pathlib import PurePosixPath

from artefact_sync import manifest as m
from artefact_sync.errors import ValidationError

SITE = {"base_url": "https://x.example/artefacts/"}


def raw(**overrides) -> dict:
    body = {
        "version": 1,
        "site": SITE,
        "protected_files": ["vendor/marked.min.js"],
        "ignored_sources": [],
        "collections": [
            {"id": "c", "title": "C", "section": "S", "section_order": 10, "order": 10}
        ],
        "entries": [
            {
                "id": "e",
                "source": "a/b.png",
                "destination": "a/b.png",
                "title": "B",
                "collection": "c",
                "order": 10,
                "replacements": {},
            }
        ],
    }
    body.update(overrides)
    return body


class SchemaTests(unittest.TestCase):
    def test_loads_a_valid_manifest(self) -> None:
        parsed = m.manifest_from_dict(raw())
        self.assertEqual(1, parsed.version)
        self.assertEqual(PurePosixPath("a/b.png"), parsed.entries[0].destination)

    def test_rejects_an_unknown_version(self) -> None:
        with self.assertRaises(ValidationError):
            m.manifest_from_dict(raw(version=99))

    def test_rejects_duplicate_destinations(self) -> None:
        body = raw()
        second = dict(body["entries"][0], id="e2", source="a/c.png")
        body["entries"] = [body["entries"][0], second]
        with self.assertRaises(ValidationError):
            m.validate_manifest(m.manifest_from_dict(body))

    def test_rejects_a_parent_traversal_destination(self) -> None:
        body = raw()
        body["entries"][0]["destination"] = "../escape.png"
        with self.assertRaises(ValidationError):
            m.validate_manifest(m.manifest_from_dict(body))

    def test_rejects_an_entry_in_an_unknown_collection(self) -> None:
        body = raw()
        body["entries"][0]["collection"] = "nope"
        with self.assertRaises(ValidationError):
            m.validate_manifest(m.manifest_from_dict(body))

    def test_collection_description_is_optional_and_absent_stays_absent(self) -> None:
        parsed = m.manifest_from_dict(raw())
        self.assertIsNone(parsed.collections[0].description)
        emitted = json.loads(m.manifest_to_json(parsed))
        self.assertNotIn("description", emitted["collections"][0])

    def test_page_template_destination_is_reserved(self) -> None:
        body = raw()
        body["entries"][0]["source"] = "page-template.html"
        body["entries"][0]["destination"] = "page-template.html"
        with self.assertRaises(ValidationError):
            m.validate_manifest(m.manifest_from_dict(body))


class NewFieldTests(unittest.TestCase):
    def test_description_and_date_survive_a_round_trip(self) -> None:
        body = raw()
        body["entries"][0]["description"] = "what it is"
        body["entries"][0]["date"] = "2026-03-28"
        once = m.manifest_from_dict(body)
        twice = m.manifest_from_bytes(m.manifest_to_json(once).encode("utf-8"))
        self.assertEqual("what it is", twice.entries[0].description)
        self.assertEqual("2026-03-28", twice.entries[0].date)

    def test_absent_description_and_date_stay_absent_in_json(self) -> None:
        emitted = json.loads(m.manifest_to_json(m.manifest_from_dict(raw())))
        self.assertNotIn("description", emitted["entries"][0])
        self.assertNotIn("date", emitted["entries"][0])

    def test_rejects_a_date_that_is_not_iso(self) -> None:
        body = raw()
        body["entries"][0]["date"] = "28/03/2026"
        with self.assertRaises(ValidationError):
            m.manifest_from_dict(body)

    def test_site_block_survives_a_round_trip(self) -> None:
        once = m.manifest_from_dict(raw())
        twice = m.manifest_from_bytes(m.manifest_to_json(once).encode("utf-8"))
        self.assertEqual(once.site, twice.site)


class ExtensionTests(unittest.TestCase):
    def test_the_new_types_are_approved(self) -> None:
        for suffix in (".pdf", ".webp", ".gif", ".svg"):
            self.assertIn(suffix, m.APPROVED_EXTENSIONS)

    def test_html_destination_must_be_a_directory_index(self) -> None:
        body = raw()
        body["entries"][0]["source"] = "a/b.html"
        body["entries"][0]["destination"] = "a/b.html"
        with self.assertRaises(ValidationError):
            m.validate_manifest(m.manifest_from_dict(body))
