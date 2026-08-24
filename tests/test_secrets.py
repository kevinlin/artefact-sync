from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePosixPath

from artefact_sync import cli, plan as p
from tests.helpers import make_repo, make_source_tree


class FilenameHeuristicTests(unittest.TestCase):
    """The requirement names the words prompts, draft, internal and client."""

    def test_a_spaced_client_filename_warns(self) -> None:
        notes = p.source_warnings(PurePosixPath("Client Presentation.pdf"), None)
        self.assertEqual(1, len(notes))
        self.assertEqual("secret", notes[0].kind)
        self.assertIn("client", notes[0].detail)

    def test_a_word_in_the_middle_of_a_name_warns(self) -> None:
        self.assertEqual(1, len(p.source_warnings(PurePosixPath("q1-internal-review.md"), "")))

    def test_a_nested_draft_warns(self) -> None:
        self.assertEqual(1, len(p.source_warnings(PurePosixPath("talk/old-drafts.md"), "")))

    def test_a_word_that_merely_starts_the_same_does_not_warn(self) -> None:
        self.assertEqual([], p.source_warnings(PurePosixPath("clientele-map.png"), None))

    def test_an_ordinary_name_does_not_warn(self) -> None:
        self.assertEqual([], p.source_warnings(PurePosixPath("talk/adoption-curve.png"), None))


class SecretShapeTests(unittest.TestCase):
    def test_an_api_key_warns_with_its_line_number(self) -> None:
        text = "intro\nkey = sk-abcdefghijklmnopqrstuvwx\n"
        notes = p.source_warnings(PurePosixPath("talk/cost-model.html"), text)
        self.assertEqual(1, len(notes))
        self.assertEqual("talk/cost-model.html:2", notes[0].where)
        self.assertIn("API key", notes[0].detail)

    def test_an_aws_key_warns(self) -> None:
        text = "AKIAIOSFODNN7EXAMPLE\n"
        self.assertEqual(1, len(p.source_warnings(PurePosixPath("a.md"), text)))

    def test_a_private_key_warns(self) -> None:
        text = "-----BEGIN RSA PRIVATE KEY-----\n"
        self.assertEqual(1, len(p.source_warnings(PurePosixPath("a.md"), text)))

    def test_a_binary_source_is_never_read_for_secrets(self) -> None:
        self.assertEqual([], p.source_warnings(PurePosixPath("curve.png"), None))


class PlanIntegrationTests(unittest.TestCase):
    def test_a_secret_in_a_source_reaches_the_plan_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {
                "internal-notes.md": b"# Notes\n\nkey = sk-abcdefghijklmnopqrstuvwx\n",
            })
            pointer = root / "pointer.json"
            cli.main(["init", "--pointer", str(pointer),
                      "--repo", str(repo), "--source", str(source)])
            context = cli.resolve_context(cli.parse_args(["plan", "--pointer", str(pointer)]))
            from artefact_sync import manifest as manifest_module
            sync_plan = p.create_sync_plan(
                context, manifest_module.load_manifest(context.artefacts_root))
            text = p.format_plan(sync_plan)
        self.assertIn("internal-notes.md:3", text)
        self.assertIn("API key", text)
        self.assertIn('filename contains "internal"', text)
