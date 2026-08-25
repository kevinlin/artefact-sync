from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from dataclasses import dataclass, field, replace
from datetime import date as date_cls
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from config import Site, site_from_dict, site_to_dict
from errors import ArtefactSyncError, ConfigError, ValidationError

MANIFEST_NAME = "manifest.json"
TEMPLATE_NAME = "page-template.html"
CATALOGUE_NAME = "index.html"
VENDOR_NAME = "marked.min.js"
SUPPORTED_VERSION = 1

DIRECTORY_INDEX_EXTENSIONS = frozenset({".html", ".md"})
APPROVED_EXTENSIONS = frozenset(
    {".html", ".md", ".png", ".jpeg", ".jpg", ".ico", ".pdf", ".webp", ".gif", ".svg"}
)
CONTROL_FILES = frozenset({MANIFEST_NAME, TEMPLATE_NAME, CATALOGUE_NAME})
PUBLIC_COMPONENT = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+)?$")
PROTECTED_COMPONENT = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def resolve_within(
    root: Path, candidate: Path, error: type[ArtefactSyncError], message: str
) -> Path:
    root = root.resolve()
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise error(message)
    return resolved


@dataclass(frozen=True)
class Collection:
    id: str
    title: str
    description: str | None
    section: str
    section_order: int
    order: int


@dataclass(frozen=True)
class Entry:
    id: str
    source: PurePosixPath
    destination: PurePosixPath
    title: str
    collection: str
    order: int
    replacements: dict[str, str] = field(default_factory=dict)
    description: str | None = None
    date: str | None = None


@dataclass(frozen=True)
class Manifest:
    version: int
    site: Site
    protected_files: tuple[PurePosixPath, ...]
    ignored_sources: tuple[str, ...]
    collections: tuple[Collection, ...]
    entries: tuple[Entry, ...]


def _safe_relative_path(value: str, field_name: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValidationError(f"{field_name} must be a safe relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValidationError(f"{field_name} must be a safe relative path")
    return path


def _safe_ignore_rule(value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError("ignored source must be a safe relative path")
    _safe_relative_path(value.rstrip("/"), "ignored source")
    return value


def _require_string(payload: dict, name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name} must be a non-empty string")
    return value


def _optional_string(payload: dict, name: str) -> str | None:
    value = payload.get(name)
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValidationError(f"{name} must be a non-empty string when present")
    return value


def _require_int(payload: dict, name: str) -> int:
    value = payload.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{name} must be an integer")
    return value


def _entry_from_dict(raw: dict) -> Entry:
    replacements = raw.get("replacements", {})
    if not isinstance(replacements, dict) or not all(
        isinstance(old, str) and old and isinstance(new, str) and new
        for old, new in replacements.items()
    ):
        raise ValidationError("replacements must map non-empty strings")
    stamp = raw.get("date")
    if stamp is not None:
        if not isinstance(stamp, str) or not ISO_DATE.match(stamp):
            raise ValidationError(f"entry {raw.get('id')!r}: date must be YYYY-MM-DD")
        try:
            date_cls.fromisoformat(stamp)
        except ValueError as error:
            raise ValidationError(f"entry {raw.get('id')!r}: {error}") from error
    return Entry(
        id=_require_string(raw, "id"),
        source=_safe_relative_path(_require_string(raw, "source"), "source"),
        destination=_safe_relative_path(_require_string(raw, "destination"), "destination"),
        title=_require_string(raw, "title"),
        collection=_require_string(raw, "collection"),
        order=_require_int(raw, "order"),
        replacements=dict(replacements),
        description=_optional_string(raw, "description"),
        date=stamp,
    )


def manifest_from_dict(payload: dict) -> Manifest:
    if not isinstance(payload, dict):
        raise ValidationError("manifest must be a JSON object")
    try:
        site_payload = payload["site"]
        protected_payload = payload["protected_files"]
        collections_payload = payload["collections"]
        entries_payload = payload["entries"]
    except KeyError as error:
        raise ValidationError(f"missing manifest field: {error.args[0]}") from error
    if not isinstance(protected_payload, list):
        raise ValidationError("protected_files must be an array")
    if not isinstance(collections_payload, list):
        raise ValidationError("collections must be an array")
    if not isinstance(entries_payload, list):
        raise ValidationError("entries must be an array")
    if not all(isinstance(item, dict) for item in collections_payload):
        raise ValidationError("each collection must be an object")
    if not all(isinstance(item, dict) for item in entries_payload):
        raise ValidationError("each entry must be an object")

    try:
        site = site_from_dict(site_payload)
    except ConfigError as error:
        raise ValidationError(str(error)) from error
    ignored_payload = payload.get("ignored_sources", [])
    if not isinstance(ignored_payload, list):
        raise ValidationError("ignored_sources must be an array")
    manifest = Manifest(
        version=payload.get("version"),
        site=site,
        protected_files=tuple(
            _safe_relative_path(value, "protected file") for value in protected_payload
        ),
        ignored_sources=tuple(_safe_ignore_rule(value) for value in ignored_payload),
        collections=tuple(
            Collection(
                id=_require_string(item, "id"),
                title=_require_string(item, "title"),
                description=_optional_string(item, "description"),
                section=_require_string(item, "section"),
                section_order=_require_int(item, "section_order"),
                order=_require_int(item, "order"),
            )
            for item in collections_payload
        ),
        entries=tuple(_entry_from_dict(item) for item in entries_payload),
    )
    validate_manifest(manifest)
    return manifest


def is_ignored(source: PurePosixPath, rules: tuple[str, ...]) -> bool:
    text = source.as_posix()
    for rule in rules:
        if rule.endswith("/"):
            directory = rule.rstrip("/")
            if ("/" not in directory and directory in source.parts[:-1]) or text.startswith(rule):
                return True
        if any(char in rule for char in "*?[") and (
            fnmatch.fnmatchcase(text, rule) or fnmatch.fnmatchcase(source.name, rule)
        ):
            return True
        if text == rule:
            return True
    return False


def _require_unique(values: list[Any], message: str) -> None:
    if len(values) != len(set(values)):
        raise ValidationError(message)


def _validate_path_components(
    path: PurePosixPath, pattern: "re.Pattern[str]", message: str
) -> None:
    if not all(pattern.fullmatch(component) for component in path.parts):
        raise ValidationError(message)


def validate_manifest(manifest: Manifest) -> None:
    if manifest.version != SUPPORTED_VERSION:
        raise ValidationError(f"version must be {SUPPORTED_VERSION}")
    _require_unique([collection.id for collection in manifest.collections], "duplicate collection id")
    _require_unique([entry.id for entry in manifest.entries], "duplicate entry id")
    _require_unique([entry.source for entry in manifest.entries], "duplicate source")
    _require_unique([entry.destination for entry in manifest.entries], "duplicate destination")
    _require_unique(list(manifest.protected_files), "duplicate protected file")
    _require_unique(list(manifest.ignored_sources), "duplicate ignored source")

    for entry in manifest.entries:
        if is_ignored(entry.source, manifest.ignored_sources):
            raise ValidationError(
                f"ignored source is also an entry source: {entry.source.as_posix()}"
            )

    collection_ids = {collection.id for collection in manifest.collections}
    reserved_destinations = {PurePosixPath(path) for path in CONTROL_FILES}
    managed_destinations = {entry.destination for entry in manifest.entries}
    protected_destinations = set(manifest.protected_files)
    if managed_destinations & reserved_destinations:
        raise ValidationError("entry destination is reserved")
    if protected_destinations & reserved_destinations:
        raise ValidationError("protected file destination is reserved")
    if protected_destinations & managed_destinations:
        raise ValidationError("protected and managed destinations must be disjoint")

    for entry in manifest.entries:
        if entry.collection not in collection_ids:
            raise ValidationError(f"unknown collection for entry {entry.id}")
        source_suffix = entry.source.suffix.lower()
        if source_suffix not in APPROVED_EXTENSIONS:
            raise ValidationError(f"unsupported source extension for entry {entry.id}")
        _validate_path_components(
            entry.destination, PUBLIC_COMPONENT, "destination must be lowercase kebab-case"
        )
        if source_suffix in DIRECTORY_INDEX_EXTENSIONS:
            if entry.destination.name != "index.html":
                raise ValidationError(
                    f"generated destination for entry {entry.id} must end in index.html"
                )
        elif entry.destination.suffix.lower() != source_suffix:
            raise ValidationError(
                f"binary destination for entry {entry.id} must keep source extension"
            )

    for path in manifest.protected_files:
        _validate_path_components(
            path, PROTECTED_COMPONENT, "protected file must use a lowercase safe path"
        )


def _renumber_colliding_orders(
    items: tuple[Any, ...], group_of: Callable[[Any], Any]
) -> tuple[Any, ...]:
    groups: dict[Any, list[int]] = {}
    for index, item in enumerate(items):
        groups.setdefault(group_of(item), []).append(index)
    renumbered = list(items)
    for indices in groups.values():
        orders = [items[index].order for index in indices]
        if len(set(orders)) == len(orders):
            continue
        ordered = sorted(indices, key=lambda index: (items[index].order, index))
        for position, index in enumerate(ordered, start=1):
            renumbered[index] = replace(items[index], order=position * 10)
    return tuple(renumbered)


def normalize_orders(manifest: Manifest) -> Manifest:
    return replace(
        manifest,
        collections=_renumber_colliding_orders(
            manifest.collections, lambda collection: collection.section
        ),
        entries=_renumber_colliding_orders(
            manifest.entries, lambda entry: entry.collection
        ),
    )


def _entry_to_dict(entry: Entry) -> dict:
    body = {
        "id": entry.id,
        "source": entry.source.as_posix(),
        "destination": entry.destination.as_posix(),
        "title": entry.title,
        "collection": entry.collection,
        "order": entry.order,
        "replacements": dict(entry.replacements),
    }
    if entry.description is not None:
        body["description"] = entry.description
    if entry.date is not None:
        body["date"] = entry.date
    return body


def manifest_to_json(manifest: Manifest) -> str:
    collections = []
    for collection in manifest.collections:
        body = {"id": collection.id, "title": collection.title}
        if collection.description is not None:
            body["description"] = collection.description
        body.update(
            section=collection.section,
            section_order=collection.section_order,
            order=collection.order,
        )
        collections.append(body)
    payload = {
        "version": manifest.version,
        "site": site_to_dict(manifest.site),
        "protected_files": [path.as_posix() for path in manifest.protected_files],
        "ignored_sources": list(manifest.ignored_sources),
        "collections": collections,
        "entries": [_entry_to_dict(entry) for entry in manifest.entries],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def manifest_from_bytes(content: bytes) -> Manifest:
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"cannot read manifest: {error}") from error
    return manifest_from_dict(payload)


def load_manifest(artefacts_root: Path) -> Manifest:
    path = artefacts_root / MANIFEST_NAME
    if not path.is_file():
        raise ValidationError(f"no manifest at {path}; run 'artefact-sync init' first")
    try:
        return manifest_from_bytes(path.read_bytes())
    except OSError as error:
        raise ValidationError(f"cannot read manifest: {error}") from error


def head_manifest(repo_root: Path) -> Manifest | None:
    """The manifest as of HEAD, or None when it was never committed or cannot be read.

    Read leniently on purpose. This value only ever feeds `check_published_invariants`,
    which reads `id`, `destination` and `title`. A repository adopting the skill has a
    committed manifest with no `site` block, so failing the whole run on a field the
    check never touches would make adoption impossible - while returning None outright
    would drop the URL-freeze guard on exactly the run where published destinations are
    at stake. Injecting a placeholder keeps the guard.
    """
    result = subprocess.run(
        ["git", "show", f"HEAD:artefacts/{MANIFEST_NAME}"],
        cwd=str(repo_root),
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict):
        payload.setdefault("site", {"base_url": "https://head.invalid/"})
    try:
        return manifest_from_dict(payload)
    except ValidationError:
        return None


def check_published_invariants(current: Manifest, head: Manifest | None) -> None:
    """Reject edits that change an existing entry's URL or title."""
    if head is None:
        return
    published = {entry.id: entry for entry in head.entries}
    problems = []
    for entry in current.entries:
        was = published.get(entry.id)
        if was is None:
            continue
        if entry.destination != was.destination:
            problems.append(
                f"entry {entry.id!r}: destination {was.destination.as_posix()} -> "
                f"{entry.destination.as_posix()} would break the published URL "
                f"for {was.destination.as_posix()}"
            )
        if entry.title != was.title:
            problems.append(
                f"entry {entry.id!r}: title {was.title!r} -> {entry.title!r}; "
                "an existing entry is never re-titled"
            )
    if problems:
        raise ValidationError("\n".join(problems))
