from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from . import manifest
from .errors import ValidationError

IGNORED_METADATA_NAMES = frozenset({".DS_Store", "Thumbs.db"})


@dataclass(frozen=True)
class SourceInventory:
    approved: tuple[PurePosixPath, ...]
    excluded: tuple[tuple[str, int], ...]


def scan_source(source_root: Path, repo_root: Path) -> SourceInventory:
    """Inventory approved files without following symlinks or entering the destination repo."""
    if not source_root.is_dir():
        raise ValidationError(f"source directory does not exist: {source_root}")
    root = source_root.resolve()
    pruned = repo_root.resolve()
    approved: list[PurePosixPath] = []
    skipped: dict[str, int] = {}

    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if not (here / name).is_symlink() and (here / name).resolve() != pruned
        )
        for name in sorted(filenames):
            path = here / name
            if path.is_symlink() or name in IGNORED_METADATA_NAMES:
                continue
            relative = PurePosixPath(path.relative_to(root).as_posix())
            suffix = path.suffix.lower()
            if suffix in manifest.APPROVED_EXTENSIONS:
                approved.append(relative)
            else:
                label = suffix or "(no suffix)"
                skipped[label] = skipped.get(label, 0) + 1
    return SourceInventory(tuple(approved), tuple(sorted(skipped.items())))


def is_ignored(source: PurePosixPath, rules: tuple[str, ...]) -> bool:
    return manifest._is_ignored(source, rules)


def apply_source_ignores(
    inventory: SourceInventory, rules: tuple[str, ...]
) -> tuple[SourceInventory, tuple[tuple[str, int], ...]]:
    kept = tuple(source for source in inventory.approved if not is_ignored(source, rules))
    counts = tuple(
        (rule, sum(1 for source in inventory.approved if is_ignored(source, (rule,))))
        for rule in rules
    )
    return replace(inventory, approved=kept), counts


_SVG_RULES: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("script element", re.compile(r"<\s*script\b", re.I)),
    ("foreignObject element", re.compile(r"<\s*foreignObject\b", re.I)),
    ("event handler attribute", re.compile(r"\bon[a-z]+\s*=", re.I)),
    (
        "external reference",
        re.compile(
            r"\b(?:xlink:)?href\s*=\s*[\"']\s*(?:[a-z][a-z0-9+.-]*:)?//",
            re.I,
        ),
    ),
    ("javascript: url", re.compile(r"[\"'(]\s*javascript\s*:", re.I)),
    ("data: url", re.compile(r"\b(?:xlink:)?href\s*=\s*[\"']\s*data\s*:", re.I)),
    (
        "external css url()",
        re.compile(r"url\(\s*[\"']?\s*(?:[a-z][a-z0-9+.-]*:)?//", re.I),
    ),
    (
        "external entity declaration",
        re.compile(r"<!ENTITY\b[^>]*\b(?:SYSTEM|PUBLIC)\b", re.I),
    ),
)


def validate_svg(data: bytes, label: str) -> None:
    """Refuse SVG scripts, handlers, and external references without rewriting bytes."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(f"{label}: not valid UTF-8 ({error})") from error

    problems = []
    for reason, pattern in _SVG_RULES:
        for match in pattern.finditer(text):
            number = text.count("\n", 0, match.start()) + 1
            problems.append(f"{label}:{number}: {reason} ({match.group(0).strip()!r})")
    problems.sort()
    if problems:
        raise ValidationError(
            "\n".join(problems)
            + "\nSVG must not contain scripts, event handlers, or external references."
        )
