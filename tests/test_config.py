from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath

import config
from errors import ConfigError


class PointerTests(unittest.TestCase):
    def test_round_trips_through_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nested" / "config.json"
            pointer = config.Pointer(Path("/r"), Path("/s"), "direct")
            config.save_pointer(pointer, target)
            self.assertEqual(pointer, config.load_pointer(target))

    def test_missing_pointer_names_the_command_that_creates_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConfigError) as caught:
                config.load_pointer(Path(tmp) / "absent.json")
        self.assertIn("init", str(caught.exception))

    def test_rejects_an_unknown_push_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_text(json.dumps({"repo": "/r", "source": "/s", "push": "yolo"}))
            with self.assertRaises(ConfigError):
                config.load_pointer(target)


class SiteTests(unittest.TestCase):
    def test_defaults_to_a_standalone_catalogue(self) -> None:
        site = config.site_from_dict({"base_url": "https://x.example/artefacts/"})
        self.assertEqual("standalone", site.catalogue_mode)
        self.assertIsNone(site.catalogue_page)

    def test_inject_mode_requires_a_page(self) -> None:
        with self.assertRaises(ConfigError):
            config.site_from_dict(
                {"base_url": "https://x.example/artefacts/", "catalogue": {"mode": "inject"}}
            )

    def test_inject_page_must_stay_inside_the_artefacts_tree(self) -> None:
        with self.assertRaises(ConfigError):
            config.site_from_dict(
                {
                    "base_url": "https://x.example/artefacts/",
                    "catalogue": {"mode": "inject", "page": "../index.html"},
                }
            )

    def test_base_url_must_end_with_a_slash(self) -> None:
        with self.assertRaises(ConfigError):
            config.site_from_dict({"base_url": "https://x.example/artefacts"})

    def test_analytics_id_must_look_like_a_ga4_measurement_id(self) -> None:
        with self.assertRaises(ConfigError):
            config.site_from_dict(
                {"base_url": "https://x.example/artefacts/", "analytics_id": "UA-12345-1"}
            )

    def test_analytics_is_off_when_the_manifest_says_nothing(self) -> None:
        site = config.site_from_dict({"base_url": "https://x.example/artefacts/"})
        self.assertEqual("", site.analytics_id)

    def test_site_survives_a_json_round_trip(self) -> None:
        site = config.site_from_dict(
            {
                "base_url": "https://x.example/artefacts/",
                "favicon": "<link rel='icon' href='data:,'>",
                "analytics_id": "G-ABCD1234XY",
                "catalogue": {"mode": "inject", "page": "index.html"},
            }
        )
        self.assertEqual(site, config.site_from_dict(config.site_to_dict(site)))
        self.assertEqual(PurePosixPath("index.html"), site.catalogue_page)


class ContextTests(unittest.TestCase):
    def test_artefacts_root_hangs_off_the_repo_not_the_cwd(self) -> None:
        pointer = config.Pointer(Path("/r"), Path("/s"), "direct")
        site = config.site_from_dict({"base_url": "https://x.example/artefacts/"})
        context = config.build_context(pointer, site)
        self.assertEqual(Path("/r/artefacts"), context.artefacts_root)
