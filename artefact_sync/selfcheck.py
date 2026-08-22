from __future__ import annotations

import string
from pathlib import Path, PurePosixPath

from .catalogue import CATALOGUE_TEMPLATE_NAME
from .config import DEFAULT_FAVICON, Site
from .errors import ValidationError
from .manifest import Entry, TEMPLATE_NAME, VENDOR_NAME
from .render import extract_markdown, load_template, render_markdown_page

# The bundled assets belong to the installed package, so this is the one lookup the
# "nothing resolves paths from __file__" rule exempts.
ASSETS = Path(__file__).resolve().parent / "assets"
REPAIR = "the install looks damaged; repair it with: git -C ~/.claude/skills/artefact-sync pull"
PROBE_MARKDOWN = b"# Probe\n\nOne $dollar, one </script> escape, one trailing newline.\n"
PAGE_FIELDS = {
    "title": "t", "favicon": "f", "prefix": "p", "vendor": "v",
    "markdown": "m", "block_start": "s", "block_end": "e",
}
CATALOGUE_FIELDS = {"title": "t", "favicon": "f", "catalogue": "c"}
MINIMUM_BYTES = {TEMPLATE_NAME: 200, CATALOGUE_TEMPLATE_NAME: 200, VENDOR_NAME: 10_000}

PROBE_SITE = Site(
    base_url="https://probe.invalid/artefacts/",
    favicon=DEFAULT_FAVICON,
    catalogue_mode="standalone",
    catalogue_page=None,
)
PROBE_ENTRY = Entry(
    id="self-check",
    source=PurePosixPath("probe.md"),
    destination=PurePosixPath("probe/index.html"),
    title="Probe",
    collection="self-check",
    order=1,
)


def _check_assets() -> None:
    for name, minimum in MINIMUM_BYTES.items():
        path = ASSETS / name
        if not path.is_file():
            raise ValidationError(f"bundled asset is missing: {path}\n\n{REPAIR}")
        size = path.stat().st_size
        if size < minimum:
            raise ValidationError(
                f"bundled asset looks truncated: {path} is {size} bytes, "
                f"expected at least {minimum}\n\n{REPAIR}"
            )


def _check_substitutes(template: string.Template, fields: dict, label: str) -> None:
    try:
        template.substitute(**fields)
    except (KeyError, ValueError) as error:
        raise ValidationError(
            f"{label} does not substitute cleanly: {error}\n\n"
            f"it must use only {', '.join('$' + name for name in sorted(fields))} "
            "and escape any other dollar sign as $$"
        ) from error


def _check_round_trip(template: string.Template, label: str) -> None:
    rendered = render_markdown_page(
        PROBE_ENTRY, PROBE_MARKDOWN, PurePosixPath("vendor") / VENDOR_NAME,
        PROBE_SITE, template,
    )
    found = extract_markdown(rendered.decode("utf-8"))
    if found != PROBE_MARKDOWN.decode("utf-8"):
        raise ValidationError(
            f"{label} broke the Markdown round trip; a page rendered from it cannot be "
            f"read back as its source\n\n{REPAIR}"
        )


def run_self_check(artefacts_root: Path | None = None) -> None:
    """Prove the installed skill can still render, before anything irreversible runs.

    Cheap on purpose: file sizes, two template substitutions, one round trip. It catches the
    corrupted or half-finished `git pull`, which no CI run on the source repository can see.
    """
    _check_assets()
    bundled = string.Template((ASSETS / TEMPLATE_NAME).read_text(encoding="utf-8"))
    _check_substitutes(bundled, PAGE_FIELDS, f"the bundled {TEMPLATE_NAME}")
    _check_round_trip(bundled, f"the bundled {TEMPLATE_NAME}")
    _check_substitutes(
        string.Template((ASSETS / CATALOGUE_TEMPLATE_NAME).read_text(encoding="utf-8")),
        CATALOGUE_FIELDS,
        f"the bundled {CATALOGUE_TEMPLATE_NAME}",
    )
    if artefacts_root is None or not (artefacts_root / TEMPLATE_NAME).is_file():
        return
    override = load_template(artefacts_root)
    _check_substitutes(override, PAGE_FIELDS, f"artefacts/{TEMPLATE_NAME}")
    _check_round_trip(override, f"artefacts/{TEMPLATE_NAME}")
