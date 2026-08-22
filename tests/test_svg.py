from __future__ import annotations

import unittest

from artefact_sync.errors import ValidationError
from artefact_sync.scan import validate_svg

CLEAN = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
  <rect width="10" height="10" fill="#0af"/>
  <text x="1" y="5">safe</text>
</svg>
"""


class SvgValidatorTests(unittest.TestCase):
    def test_a_clean_svg_passes(self) -> None:
        validate_svg(CLEAN, "diagrams/ok.svg")

    def test_rejects_a_script_element_and_names_the_line(self) -> None:
        data = b'<svg>\n  <rect/>\n  <script>alert(1)</script>\n</svg>\n'
        with self.assertRaises(ValidationError) as caught:
            validate_svg(data, "d/x.svg")
        self.assertIn("d/x.svg:3", str(caught.exception))
        self.assertIn("script", str(caught.exception))

    def test_rejects_an_on_handler(self) -> None:
        data = b'<svg>\n  <rect onload="go()"/>\n</svg>\n'
        with self.assertRaises(ValidationError) as caught:
            validate_svg(data, "d/x.svg")
        self.assertIn("d/x.svg:2", str(caught.exception))
        self.assertIn("onload", str(caught.exception))

    def test_rejects_an_external_reference(self) -> None:
        data = b'<svg>\n  <image href="https://evil.example/a.png"/>\n</svg>\n'
        with self.assertRaises(ValidationError):
            validate_svg(data, "d/x.svg")

    def test_rejects_an_external_reference_split_across_lines(self) -> None:
        data = b'<svg>\n  <image href=\n    "https://evil.example/a.png"/>\n</svg>\n'
        with self.assertRaises(ValidationError) as caught:
            validate_svg(data, "d/x.svg")
        self.assertIn("d/x.svg:2", str(caught.exception))

    def test_rejects_an_xlink_external_reference(self) -> None:
        data = b'<svg>\n  <use xlink:href="http://evil.example/a#b"/>\n</svg>\n'
        with self.assertRaises(ValidationError):
            validate_svg(data, "d/x.svg")

    def test_rejects_a_javascript_url(self) -> None:
        data = b'<svg>\n  <a href="javascript:alert(1)">x</a>\n</svg>\n'
        with self.assertRaises(ValidationError):
            validate_svg(data, "d/x.svg")

    def test_rejects_foreign_object(self) -> None:
        data = b'<svg>\n  <foreignObject><body/></foreignObject>\n</svg>\n'
        with self.assertRaises(ValidationError):
            validate_svg(data, "d/x.svg")

    def test_rejects_a_css_url_pointing_off_site(self) -> None:
        data = b'<svg>\n  <style>@import url(https://evil.example/a.css);</style>\n</svg>\n'
        with self.assertRaises(ValidationError):
            validate_svg(data, "d/x.svg")

    def test_rejects_an_external_entity_declaration(self) -> None:
        data = b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>\n<svg/>\n'
        with self.assertRaises(ValidationError):
            validate_svg(data, "d/x.svg")

    def test_rejects_bytes_that_are_not_utf8(self) -> None:
        with self.assertRaises(ValidationError):
            validate_svg(b"\xff\xfe<svg/>", "d/x.svg")

    def test_reports_every_problem_not_just_the_first(self) -> None:
        data = b'<svg>\n  <script/>\n  <rect onclick="x()"/>\n</svg>\n'
        with self.assertRaises(ValidationError) as caught:
            validate_svg(data, "d/x.svg")
        message = str(caught.exception)
        self.assertIn("d/x.svg:2", message)
        self.assertIn("d/x.svg:3", message)
