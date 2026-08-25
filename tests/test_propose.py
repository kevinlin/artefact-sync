from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePosixPath

import propose
from config import site_from_dict
from manifest import Collection, Entry, Manifest
from tests.helpers import make_source_tree


class DestinationTests(unittest.TestCase):
    def test_lowercases_and_kebabs_a_spaced_filename(self) -> None:
        self.assertEqual(
            PurePosixPath("talk/adoption-curve.png"),
            propose.suggest_destination(PurePosixPath("talk/Adoption Curve.png")),
        )

    def test_markdown_becomes_a_directory_index(self) -> None:
        self.assertEqual(
            PurePosixPath("talk/notes/index.html"),
            propose.suggest_destination(PurePosixPath("talk/Notes.md")),
        )

    def test_html_becomes_a_directory_index(self) -> None:
        self.assertEqual(
            PurePosixPath("talk/cost-model/index.html"),
            propose.suggest_destination(PurePosixPath("talk/cost-model.html")),
        )


class RenameTests(unittest.TestCase):
    def test_identical_bytes_are_treated_as_a_rename_and_keep_the_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), {"d/Deploy Flow v3.png": b"IDENTICAL"})
            renames = propose.detect_renames(
                missing={PurePosixPath("d/Deploy Flow.png"): PurePosixPath("d/deploy-flow.png")},
                unlisted=(PurePosixPath("d/Deploy Flow v3.png"),),
                published={PurePosixPath("d/deploy-flow.png"): b"IDENTICAL"},
                source_root=source,
            )
        self.assertEqual(
            {PurePosixPath("d/Deploy Flow v3.png"): PurePosixPath("d/deploy-flow.png")}, renames
        )

    def test_different_bytes_are_not_a_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), {"d/new.png": b"DIFFERENT"})
            renames = propose.detect_renames(
                missing={PurePosixPath("d/old.png"): PurePosixPath("d/old.png")},
                unlisted=(PurePosixPath("d/new.png"),),
                published={PurePosixPath("d/old.png"): b"ORIGINAL"},
                source_root=source,
            )
        self.assertEqual({}, renames)

    def test_a_rename_is_never_guessed_when_two_candidates_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), {"a.png": b"SAME", "b.png": b"SAME"})
            renames = propose.detect_renames(
                missing={PurePosixPath("old.png"): PurePosixPath("old.png")},
                unlisted=(PurePosixPath("a.png"), PurePosixPath("b.png")),
                published={PurePosixPath("old.png"): b"SAME"},
                source_root=source,
            )
        self.assertEqual({}, renames)


class ProposalTests(unittest.TestCase):
    def test_a_renamed_source_keeps_its_published_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_root = make_source_tree(Path(tmp), {"d/new.png": b"SAME"})
            old = Entry(
                id="old", source=PurePosixPath("d/old.png"),
                destination=PurePosixPath("d/stable.png"), title="Stable title",
                collection="c", order=10, replacements={},
            )
            manifest = Manifest(
                version=1,
                site=site_from_dict({"base_url": "https://x.example/artefacts/"}),
                protected_files=(), ignored_sources=(),
                collections=(Collection("c", "C", None, "Artefacts", 10, 10),),
                entries=(old,),
            )
            result = propose.propose_manifest_additions(
                manifest,
                (PurePosixPath("d/new.png"),),
                {PurePosixPath("d/new.png"): PurePosixPath("d/stable.png")},
                source_root,
            )
        self.assertEqual(PurePosixPath("d/new.png"), result.entries[0].source)
        self.assertEqual(PurePosixPath("d/stable.png"), result.entries[0].destination)
        self.assertEqual("Stable title", result.entries[0].title)


SITE = site_from_dict({"base_url": "https://x.example/artefacts/"})


class RootCollectionTests(unittest.TestCase):
    def _propose(self, files: dict) -> Manifest:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), files)
            empty = Manifest(1, SITE, (), (), (), ())
            return propose.propose_manifest_additions(
                empty,
                tuple(PurePosixPath(name) for name in sorted(files)),
                {},
                source,
            )

    def test_root_level_sources_are_not_named_after_their_first_file(self) -> None:
        result = self._propose({"curve.png": b"1", "note.md": b"# Note\n"})
        self.assertEqual(("general",), tuple(c.id for c in result.collections))
        self.assertEqual(("General",), tuple(c.title for c in result.collections))
        self.assertEqual({"general"}, {entry.collection for entry in result.entries})

    def test_a_subdirectory_still_names_its_own_collection(self) -> None:
        result = self._propose({"talk/curve.png": b"1"})
        self.assertEqual(("talk",), tuple(c.id for c in result.collections))
        self.assertEqual(("Talk",), tuple(c.title for c in result.collections))
