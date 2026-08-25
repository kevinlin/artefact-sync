from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

import catalogue, config, manifest, plan as plan_module, render, scan
from errors import ValidationError


class _ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del tag
        for name, value in attrs:
            if value is None:
                continue
            if name == "href":
                self.hrefs.append(value)
                self.references.append(value)
            elif name == "src":
                self.references.append(value)


def _parse_references(text: str) -> _ReferenceParser:
    parser = _ReferenceParser()
    parser.feed(text)
    parser.close()
    return parser


def _local_reference(context: config.Context, page: Path, reference: str) -> Path | None:
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    path = unquote(parsed.path)
    target = context.repo_root / path.lstrip("/") if path.startswith("/") else page.parent / path
    if path.endswith("/") or target.is_dir():
        target /= "index.html"
    resolved = target.resolve()
    if not resolved.is_relative_to(context.repo_root.resolve()):
        raise ValidationError(f"local reference escapes repository: {reference}")
    return resolved


def validate_repository(
    context: config.Context, current: manifest.Manifest
) -> tuple[plan_module.Note, ...]:
    catalogue_path = (
        PurePosixPath(manifest.CATALOGUE_NAME)
        if context.site.catalogue_mode == "standalone"
        else context.site.catalogue_page
    )
    if catalogue_path is None:
        raise ValidationError("site.catalogue inject mode needs a page")
    expected = {
        *(PurePosixPath(name) for name in manifest.CONTROL_FILES),
        catalogue_path,
        *current.protected_files,
        *(entry.destination for entry in current.entries),
    }
    actual = plan_module.scan_published_tree(context.artefacts_root)
    missing = sorted(expected - actual, key=str)
    if missing:
        raise ValidationError(
            "missing published file: " + ", ".join(path.as_posix() for path in missing)
        )

    notes = [
        plan_module.Note(
            "orphan",
            f"artefacts/{path.as_posix()}",
            "in repo, in no manifest, left alone",
        )
        for path in sorted(actual - expected, key=str)
    ]

    try:
        catalogue_document = (context.artefacts_root / catalogue_path.as_posix()).read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeError) as error:
        raise ValidationError(f"cannot read catalogue: {error}") from error
    href_counts = Counter(_parse_references(catalogue_document).hrefs)
    for entry in current.entries:
        href = catalogue.public_href(entry)
        if href_counts[href] != 1:
            raise ValidationError(
                f"catalogue link for {entry.id} must appear exactly once, found {href_counts[href]}"
            )

    for relative in sorted(actual, key=str):
        path = context.artefacts_root / relative.as_posix()
        if relative.suffix.lower() == ".svg":
            scan.validate_svg(path.read_bytes(), f"artefacts/{relative.as_posix()}")
        if relative.suffix.lower() != ".html" or relative == PurePosixPath(manifest.TEMPLATE_NAME):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise ValidationError(f"cannot parse HTML file {path}: {error}") from error
        for line, url in render.external_references(text):
            notes.append(plan_module.external_note(f"artefacts/{relative}:{line}", url))
        for reference in _parse_references(text).references:
            target = _local_reference(context, path, reference)
            if target is not None and not target.is_file():
                raise ValidationError(f"broken local reference in {relative}: {reference}")
    return tuple(notes)
