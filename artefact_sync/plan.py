from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import PurePosixPath

from . import catalogue, manifest as manifest_module, propose, render, scan
from .config import Context
from .errors import ValidationError
from .manifest import Entry, Manifest

DELETION_KINDS = frozenset({"delete"})
WRITE_KINDS = frozenset({"add", "update"})
LARGE_FILE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class Change:
    kind: str
    destination: PurePosixPath
    source: PurePosixPath | None
    size: int | None
    url: str
    diff: str | None


@dataclass(frozen=True)
class Note:
    kind: str
    where: str
    detail: str


@dataclass(frozen=True)
class Blocked:
    where: str
    detail: str


@dataclass(frozen=True)
class SyncPlan:
    changes: tuple[Change, ...]
    notes: tuple[Note, ...]
    blocked: tuple[Blocked, ...]
    desired_files: dict[PurePosixPath, bytes]
    next_manifest: Manifest | None
    # Two of the closed allowlist's three outcomes. Defaulted so M1/M2 constructions still work.
    excluded: tuple[tuple[str, int], ...] = ()
    ignored: tuple[tuple[str, int], ...] = ()


def _public_href(destination: PurePosixPath) -> str:
    if destination.name == "index.html":
        parent = destination.parent.as_posix()
        return "" if parent == "." else parent.rstrip("/") + "/"
    return destination.as_posix()


def _public_url(context: Context, destination: PurePosixPath) -> str:
    return context.site.base_url + _public_href(destination)


def scan_published_tree(artefacts_root) -> set[PurePosixPath]:
    published = set()
    if not artefacts_root.is_dir():
        return published
    for path in artefacts_root.rglob("*"):
        if path.is_file() and path.name not in scan.IGNORED_METADATA_NAMES:
            published.add(PurePosixPath(path.relative_to(artefacts_root).as_posix()))
    return published


def _stamp_missing_dates(manifest: Manifest, context: Context) -> Manifest:
    entries = []
    for entry in manifest.entries:
        source = context.source_root / entry.source.as_posix()
        if entry.date is None and source.is_file():
            try:
                stamp = date.fromtimestamp(source.stat().st_mtime).isoformat()
            except OSError:
                stamp = None
            entries.append(replace(entry, date=stamp) if stamp else entry)
        else:
            entries.append(entry)
    return replace(manifest, entries=tuple(entries))


def _svg_blocks(entry: Entry, data: bytes) -> list[Blocked]:
    try:
        scan.validate_svg(data, entry.source.as_posix())
    except ValidationError as error:
        blocks = []
        for line in str(error).splitlines():
            parts = line.split(":", 2)
            if len(parts) == 3 and parts[1].isdigit():
                blocks.append(Blocked(f"{parts[0]}:{parts[1]}", parts[2].strip()))
        return blocks or [Blocked(entry.source.as_posix(), str(error))]
    return []


_SECRET_RULES = (
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "looks like an AWS access key"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "looks like an API key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "contains a private key"),
    (re.compile(r"\bghp_[A-Za-z0-9]{36}\b"), "looks like a GitHub token"),
    (re.compile(r"\b[a-fA-F0-9]{40,}\b"), "contains a long hexadecimal secret shape"),
)
# Word-boundary, not component-prefix: the shipped rule missed "Client Presentation.pdf",
# "Internal Notes.html" and "q1-internal-review.md", which are the shapes a real folder holds.
_PRIVATE_WORD = re.compile(r"(?<![a-z0-9])(?:prompts?|drafts?|internal|client)(?![a-z0-9])", re.I)

TEXT_SUFFIXES = frozenset({".html", ".md", ".svg"})


def external_note(where: str, url: str) -> Note:
    return Note("external", where, f"loads {url} at runtime")


def source_warnings(source: PurePosixPath, text: str | None) -> list[Note]:
    """Filename heuristics plus secret shapes for one source. `text` is None for binary sources."""
    label = source.as_posix()
    notes = []
    match = _PRIVATE_WORD.search(label)
    if match is not None:
        notes.append(Note("secret", label, f'filename contains "{match.group(0).lower()}"'))
    if text is None:
        return notes
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern, detail in _SECRET_RULES:
            if pattern.search(line):
                notes.append(Note("secret", f"{label}:{number}", detail))
    return notes


def _source_notes(context: Context, manifest: Manifest, desired_files) -> list[Note]:
    notes = []
    for entry in manifest.entries:
        text = None
        if entry.source.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = (context.source_root / entry.source.as_posix()).read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                text = None
        notes.extend(source_warnings(entry.source, text))
        if entry.source.suffix.lower() != ".html":
            continue
        rendered = desired_files.get(entry.destination)
        if rendered is None:
            continue
        try:
            document = rendered.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for number, url in render.external_references(document):
            notes.append(external_note(f"{entry.source}:{number}", url))
    return notes


def create_sync_plan(
    context: Context, manifest: Manifest, accepted: tuple[PurePosixPath, ...] = ()
) -> SyncPlan:
    declared = manifest_module.normalize_orders(manifest)
    inventory, ignore_counts = scan.apply_source_ignores(
        scan.scan_source(context.source_root, context.repo_root), declared.ignored_sources
    )
    approved = set(inventory.approved)
    manifest_sources = {entry.source for entry in declared.entries}
    unlisted = tuple(sorted(approved - manifest_sources, key=str))
    missing_entries = tuple(entry for entry in declared.entries if entry.source not in approved)
    missing = {entry.source: entry.destination for entry in missing_entries}
    published_bytes = {}
    for entry in missing_entries:
        path = context.artefacts_root / entry.destination.as_posix()
        if path.is_file():
            published_bytes[entry.destination] = path.read_bytes()
    renames = propose.detect_renames(
        missing, unlisted, published_bytes, context.source_root
    )
    next_manifest = propose.propose_manifest_additions(
        declared, unlisted, renames, context.source_root
    )
    next_manifest = _stamp_missing_dates(next_manifest, context)
    manifest_module.check_published_invariants(
        next_manifest, manifest_module.head_manifest(context.repo_root)
    )

    # `accepted` holds sources the user named on the command line, so their proposal is not a
    # decision the run has to stop for. Every other unlisted source still blocks.
    blocked = [
        Blocked(source.as_posix(), "approved source has no manifest entry; proposal generated")
        for source in unlisted
        if source not in renames and source not in accepted
    ]
    for entry in next_manifest.entries:
        if entry.source.suffix.lower() != ".svg":
            continue
        path = context.source_root / entry.source.as_posix()
        if path.is_file():
            blocked.extend(_svg_blocks(entry, path.read_bytes()))
    for protected in next_manifest.protected_files:
        path = context.artefacts_root / protected.as_posix()
        if not path.is_file() or path.is_symlink():
            blocked.append(Blocked(protected.as_posix(), "missing protected file"))

    template = render.load_template(context.artefacts_root)
    desired_files = render.build_desired_files(context, next_manifest, template)
    if context.site.catalogue_mode == "standalone":
        catalogue_path = PurePosixPath(manifest_module.CATALOGUE_NAME)
        desired_files[catalogue_path] = catalogue.render_standalone_catalogue(
            next_manifest, context.site
        )
    else:
        if context.site.catalogue_page is None:
            raise ValidationError("site.catalogue inject mode needs a page")
        catalogue_path = context.site.catalogue_page
        target = context.artefacts_root / catalogue_path.as_posix()
        try:
            document = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise ValidationError(f"cannot read catalogue at {target}: {error}") from error
        desired_files[catalogue_path] = catalogue.replace_generated_catalogue(
            document, catalogue.render_catalogue(next_manifest, context.site)
        ).encode("utf-8")
    desired_files[PurePosixPath(manifest_module.MANIFEST_NAME)] = (
        manifest_module.manifest_to_json(next_manifest).encode("utf-8")
    )

    source_by_destination = {entry.destination: entry.source for entry in next_manifest.entries}
    changes = []
    for destination, content in sorted(desired_files.items(), key=lambda item: str(item[0])):
        path = context.artefacts_root / destination.as_posix()
        current = path.read_bytes() if path.is_file() else None
        if current == content:
            continue
        kind = "add" if current is None else "update"
        source = source_by_destination.get(destination)
        diff = None
        if kind == "update" and source is not None and source.suffix.lower() == ".md":
            diff = render.markdown_diff(current, content) or None
        changes.append(
            Change(
                kind,
                destination,
                source,
                len(content),
                _public_url(context, destination),
                diff,
            )
        )

    retained = {*desired_files, *next_manifest.protected_files}
    deletion_candidates = {entry.destination for entry in declared.entries}
    head = manifest_module.head_manifest(context.repo_root)
    if head is not None:
        deletion_candidates.update(entry.destination for entry in head.entries)
    for destination in sorted(deletion_candidates - retained, key=str):
        if (context.artefacts_root / destination.as_posix()).is_file():
            changes.append(
                Change(
                    "delete",
                    destination,
                    None,
                    None,
                    _public_url(context, destination),
                    None,
                )
            )

    notes = _source_notes(context, next_manifest, desired_files)
    # A destination queued for deletion is managed, not unmanaged. Warning that it is being
    # "left alone" would print design invariant 4 about the one file this run removes.
    expected = {
        *desired_files,
        *next_manifest.protected_files,
        *(change.destination for change in changes if change.kind in DELETION_KINDS),
        *(PurePosixPath(name) for name in manifest_module.CONTROL_FILES),
    }
    for destination in sorted(scan_published_tree(context.artefacts_root) - expected, key=str):
        notes.append(
            Note(
                "orphan",
                f"artefacts/{destination.as_posix()}",
                "in repo, in no manifest, left alone",
            )
        )
    for change in changes:
        if change.kind == "add" and change.size is not None and change.size > LARGE_FILE_BYTES:
            notes.append(Note("size", change.url, "new public file is over 10 MB"))

    return SyncPlan(
        changes=tuple(changes),
        notes=tuple(notes),
        blocked=tuple(blocked),
        desired_files=desired_files,
        next_manifest=next_manifest,
        excluded=inventory.excluded,
        ignored=tuple((rule, count) for rule, count in ignore_counts if count),
    )


_GROUPS = (
    ("NEW PUBLIC URLS", ("add",)),
    ("CHANGED", ("update",)),
    ("WILL START 404-ING", ("delete",)),
)


def _human_size(count: int) -> str:
    for unit, step in (("MB", 1024 * 1024), ("KB", 1024)):
        if count >= step:
            return f"{count / step:.1f} {unit}"
    return f"{count} B"


def format_plan(plan: SyncPlan) -> str:
    blocks = []
    for heading, kinds in _GROUPS:
        rows = [change for change in plan.changes if change.kind in kinds]
        if not rows:
            continue
        lines = [f"{heading} ({len(rows)})"]
        for change in sorted(rows, key=lambda item: item.url):
            detail = ""
            if change.kind == "add" and change.size is not None:
                detail = _human_size(change.size)
            elif change.diff:
                detail = change.diff
            elif change.kind == "delete":
                detail = "source deleted"
            lines.append(f"  {change.url}{'  ' + detail if detail else ''}")
        blocks.append("\n".join(lines))

    excluded_rows = [(label, count, "unsupported type") for label, count in plan.excluded]
    excluded_rows += [
        (rule, count, "matched an ignored source rule") for rule, count in plan.ignored
    ]
    if excluded_rows:
        lines = [f"EXCLUDED ({sum(count for _, count, _ in excluded_rows)})"]
        for label, count, reason in excluded_rows:
            files = "1 file" if count == 1 else f"{count} files"
            lines.append(f"  {label:<14} {files}, {reason}")
        blocks.append("\n".join(lines))

    if plan.notes:
        lines = [f"WARNINGS ({len(plan.notes)})"]
        for note in sorted(plan.notes, key=lambda item: (item.kind, item.where)):
            lines.append(f"  {note.kind:<9} {note.where}    {note.detail}")
        blocks.append("\n".join(lines))

    if plan.blocked:
        lines = [f"BLOCKED ({len(plan.blocked)})"]
        for item in plan.blocked:
            lines.append(f"  {item.where}   {item.detail}")
        blocks.append("\n".join(lines))

    if not blocks:
        return "no changes.\n"
    return "\n\n".join(blocks) + "\n"
