from __future__ import annotations

import html
import string
from pathlib import Path

from .config import Site
from .errors import ValidationError
from .manifest import Entry, Manifest

CATALOGUE_START = "<!-- ARTEFACTS:START -->"
CATALOGUE_END = "<!-- ARTEFACTS:END -->"


def _invert(stamp: str) -> str:
    return "".join(chr(ord("9") - int(char)) if char.isdigit() else char for char in stamp)


def entry_sort_key(entry: Entry) -> tuple:
    return (
        entry.date is None,
        "" if entry.date is None else _invert(entry.date),
        entry.order,
        entry.title,
    )


def public_href(entry: Entry) -> str:
    if entry.destination.name == "index.html":
        return entry.destination.parent.as_posix().rstrip("/") + "/"
    return entry.destination.as_posix()


def render_catalogue(manifest: Manifest, site: Site) -> str:
    # Hrefs stay relative so the same generated tree works at any site.base_url.
    entries_by_collection: dict[str, list[Entry]] = {}
    for entry in manifest.entries:
        entries_by_collection.setdefault(entry.collection, []).append(entry)

    sections: dict[tuple[int, str], list] = {}
    for collection in manifest.collections:
        if entries_by_collection.get(collection.id):
            sections.setdefault((collection.section_order, collection.section), []).append(collection)

    lines = []
    for (_, section_title), collections in sorted(sections.items()):
        lines.extend(
            [
                '<section class="catalogue-section">',
                f"  <h2>{html.escape(section_title)}</h2>",
                '  <div class="catalogue-grid">',
            ]
        )
        for collection in sorted(collections, key=lambda item: (item.order, item.title)):
            lines.extend(
                [
                    '    <article class="catalogue-card">',
                    f"      <h3>{html.escape(collection.title)}</h3>",
                ]
            )
            if collection.description is not None:
                lines.append(f"      <p>{html.escape(collection.description)}</p>")
            lines.append("      <ul>")
            for entry in sorted(entries_by_collection[collection.id], key=entry_sort_key):
                href = html.escape(public_href(entry), quote=True)
                title = html.escape(entry.title)
                lines.append(f'        <li><a href="{href}">{title}</a></li>')
            lines.extend(["      </ul>", "    </article>"])
        lines.extend(["  </div>", "</section>"])
    return "\n".join(lines)


def replace_generated_catalogue(document: str, fragment: str) -> str:
    if document.count(CATALOGUE_START) != 1 or document.count(CATALOGUE_END) != 1:
        raise ValidationError("catalogue must contain exactly one marker pair")
    start = document.index(CATALOGUE_START) + len(CATALOGUE_START)
    end = document.index(CATALOGUE_END)
    if start > end:
        raise ValidationError("catalogue markers are out of order")
    end_line_start = document.rfind("\n", 0, end) + 1
    indentation = document[end_line_start:end]
    if indentation.strip():
        raise ValidationError("end marker must start on its own line")
    return document[:start] + "\n" + fragment + "\n" + indentation + document[end:]


def render_standalone_catalogue(manifest: Manifest, site: Site) -> bytes:
    path = Path(__file__).resolve().parent / "assets" / "catalogue-template.html"
    template = string.Template(path.read_text(encoding="utf-8"))
    document = template.substitute(
        title="Artefacts",
        favicon=site.favicon,
        catalogue=render_catalogue(manifest, site),
    )
    return document.encode("utf-8")
