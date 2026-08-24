from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from pathlib import Path, PurePosixPath

from .errors import ValidationError
from .manifest import Collection, DIRECTORY_INDEX_EXTENSIONS, Entry, Manifest, validate_manifest

DEFAULT_SECTION = "Artefacts"
DEFAULT_DESCRIPTION = None
# Root-level sources have no directory to name their collection after. Naming it for whichever
# file sorts first is arbitrary, and the arbitrary run is the first one a new user sees.
ROOT_COLLECTION_LABEL = "General"
SLUG_SEPARATOR = re.compile(r"[^a-z0-9]+")
LEADING_NUMBER = re.compile(r"^\d+[-_ ]+")
WORD_SEPARATOR = re.compile(r"[-_]+")
REPEATED_SPACE = re.compile(r"\s+")
MARKDOWN_HEADING = re.compile(r"^#[ \t]+(\S.*?)[ \t]*#*[ \t]*$", re.MULTILINE)


def _slug(value: str) -> str:
    slug = SLUG_SEPARATOR.sub("-", value.lower()).strip("-")
    if not slug:
        raise ValidationError(f"cannot normalise path component: {value}")
    return slug


def suggest_destination(source: PurePosixPath) -> PurePosixPath:
    parent_parts = tuple(_slug(part) for part in source.parent.parts if part != ".")
    stem = _slug(source.stem)
    suffix = source.suffix.lower()
    if suffix in DIRECTORY_INDEX_EXTENSIONS:
        return PurePosixPath(*parent_parts, stem, "index.html")
    return PurePosixPath(*parent_parts, f"{stem}{suffix}")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_renames(
    missing: dict[PurePosixPath, PurePosixPath],
    unlisted: tuple[PurePosixPath, ...],
    published: dict[PurePosixPath, bytes],
    source_root: Path,
) -> dict[PurePosixPath, PurePosixPath]:
    new_by_digest: dict[str, list[PurePosixPath]] = {}
    for source in unlisted:
        try:
            digest = _digest((source_root / source.as_posix()).read_bytes())
        except OSError:
            continue
        new_by_digest.setdefault(digest, []).append(source)

    old_by_digest: dict[str, list[PurePosixPath]] = {}
    for destination in missing.values():
        data = published.get(destination)
        if data is not None:
            old_by_digest.setdefault(_digest(data), []).append(destination)

    return {
        new_sources[0]: old_by_digest[digest][0]
        for digest, new_sources in new_by_digest.items()
        if len(new_sources) == 1 and len(old_by_digest.get(digest, ())) == 1
    }


def _normalise_words(stem: str) -> str:
    text = REPEATED_SPACE.sub(" ", WORD_SEPARATOR.sub(" ", LEADING_NUMBER.sub("", stem))).strip()
    if not text:
        raise ValidationError(f"cannot derive a title from: {stem}")
    return text


def _derive_title(stem: str) -> str:
    text = _normalise_words(stem)
    return text[0].upper() + text[1:]


def _markdown_title(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    match = MARKDOWN_HEADING.search(text)
    return match.group(1) if match else None


def _unique_id(base: str, taken: set[str]) -> str:
    candidate = base
    number = 1
    while candidate in taken:
        number += 1
        candidate = f"{base}-{number}"
    return candidate


def _entry_id(destination: PurePosixPath, taken: set[str]) -> str:
    parts = destination.parent.parts if destination.name == "index.html" else (
        *destination.parent.parts,
        destination.stem,
    )
    return _unique_id(_slug("-".join(parts)), taken)


def _source_group(source: PurePosixPath) -> str:
    return source.parts[0] if len(source.parts) > 1 else ""


def propose_manifest_additions(
    manifest: Manifest,
    unlisted: tuple[PurePosixPath, ...],
    renames: dict[PurePosixPath, PurePosixPath],
    source_root: Path,
) -> Manifest:
    """Update exact renames, drop other vanished sources, and add unseen files."""
    source_for_destination = {destination: source for source, destination in renames.items()}
    entries = []
    for entry in manifest.entries:
        if (source_root / entry.source.as_posix()).is_file():
            entries.append(entry)
        elif entry.destination in source_for_destination:
            entries.append(replace(entry, source=source_for_destination[entry.destination]))

    remaining = tuple(source for source in unlisted if source not in renames)
    collections = list(manifest.collections)
    collection_by_group = {_source_group(entry.source): entry.collection for entry in entries}
    collection_ids = {collection.id for collection in collections}
    taken_ids = {entry.id for entry in entries}
    entry_orders = {collection.id: 0 for collection in collections}
    for entry in entries:
        entry_orders[entry.collection] = max(entry_orders.get(entry.collection, 0), entry.order)
    section_orders = {collection.section: collection.section_order for collection in collections}
    default_section_order = section_orders.get(
        DEFAULT_SECTION, max(section_orders.values(), default=0) + 10
    )
    collection_order = max(
        (collection.order for collection in collections if collection.section == DEFAULT_SECTION),
        default=0,
    )

    grouped: dict[str, list[PurePosixPath]] = {}
    for source in sorted(remaining, key=str):
        grouped.setdefault(_source_group(source), []).append(source)

    for group, sources in grouped.items():
        collection_id = collection_by_group.get(group)
        if collection_id is None and group and _slug(group) in collection_ids:
            collection_id = _slug(group)
        if collection_id is None:
            label = group or ROOT_COLLECTION_LABEL
            collection_id = _unique_id(_slug(label), collection_ids)
            collection_ids.add(collection_id)
            collection_order += 10
            collections.append(
                Collection(
                    id=collection_id,
                    title=_normalise_words(label).title(),
                    description=DEFAULT_DESCRIPTION,
                    section=DEFAULT_SECTION,
                    section_order=default_section_order,
                    order=collection_order,
                )
            )
            collection_by_group[group] = collection_id

        for source in sources:
            destination = suggest_destination(source)
            entry_orders[collection_id] = entry_orders.get(collection_id, 0) + 10
            source_path = source_root / source.as_posix()
            title = _derive_title(source.stem)
            if source.suffix.lower() == ".md":
                title = _markdown_title(source_path) or title
            entry_id = _entry_id(destination, taken_ids)
            taken_ids.add(entry_id)
            entries.append(
                Entry(
                    id=entry_id,
                    source=source,
                    destination=destination,
                    title=title,
                    collection=collection_id,
                    order=entry_orders[collection_id],
                    replacements={},
                )
            )

    result = replace(manifest, collections=tuple(collections), entries=tuple(entries))
    validate_manifest(result)
    return result
