from __future__ import annotations

import html
import re
import string

from config import ASSETS, Site
from errors import ValidationError
from manifest import Entry, Manifest
from render import ensure_analytics

CATALOGUE_START = "<!-- ARTEFACTS:START -->"
CATALOGUE_END = "<!-- ARTEFACTS:END -->"
CATALOGUE_TEMPLATE_NAME = "catalogue-template.html"


_SLUG = re.compile(r"[^a-z0-9]+")


def section_slug(value: str) -> str:
    return _SLUG.sub("-", value.lower()).strip("-")


def public_href(entry: Entry) -> str:
    if entry.destination.name == "index.html":
        return entry.destination.parent.as_posix().rstrip("/") + "/"
    return entry.destination.as_posix()


def render_catalogue(manifest: Manifest, site: Site) -> str:
    """The fragment a host page styles. Markup and ordering follow the prior art.

    Hrefs stay relative so the same generated tree works at any site.base_url. Cards
    lead with their newest entry's date because that answers "is this collection
    fresh"; entries inside a card keep their declared order, which is editorial.
    """
    entries_by_collection: dict[str, list[Entry]] = {}
    for entry in manifest.entries:
        entries_by_collection.setdefault(entry.collection, []).append(entry)

    sections: dict[tuple[int, str], list] = {}
    for collection in manifest.collections:
        if entries_by_collection.get(collection.id):
            sections.setdefault(
                (collection.section_order, collection.section), []
            ).append(collection)

    latest = {
        collection_id: max((entry.date for entry in entries if entry.date), default="")
        for collection_id, entries in entries_by_collection.items()
    }

    lines: list[str] = []
    for (_, section_title), collections in sorted(sections.items()):
        heading_id = f"{section_slug(section_title)}-heading"
        lines.extend(
            [
                f'        <section aria-labelledby="{heading_id}">',
                f'            <h2 id="{heading_id}">{html.escape(section_title)}</h2>',
                '            <div class="card-grid">',
            ]
        )
        # Newest card first, with `order` as the tie-break: Python's sort is stable and
        # reverse=True does not reverse equal elements. An undated card sorts as "" and
        # lands last.
        cards = sorted(collections, key=lambda item: item.order)
        cards.sort(key=lambda item: latest[item.id], reverse=True)
        for collection in cards:
            lines.extend(
                [
                    '                <article class="card">',
                    f"                    <h3>{html.escape(collection.title)}</h3>",
                ]
            )
            if collection.description is not None:
                lines.append(f"                    <p>{html.escape(collection.description)}</p>")
            stamp = latest[collection.id]
            if stamp:
                lines.append(
                    '                    <p class="card-updated">Updated '
                    f'<time datetime="{stamp}">{stamp}</time></p>'
                )
            lines.append("                    <ul>")
            for entry in sorted(entries_by_collection[collection.id], key=lambda e: e.order):
                href = html.escape(public_href(entry), quote=True)
                lines.append(
                    f'                        <li><a href="{href}">'
                    f"{html.escape(entry.title)}</a></li>"
                )
            lines.extend(["                    </ul>", "                </article>"])
        lines.extend(["            </div>", "        </section>"])
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
    path = ASSETS / CATALOGUE_TEMPLATE_NAME
    template = string.Template(path.read_text(encoding="utf-8"))
    document = template.substitute(
        title="Artefacts",
        favicon=site.favicon,
        catalogue=render_catalogue(manifest, site),
    )
    return ensure_analytics(document, site.analytics_id).encode("utf-8")
