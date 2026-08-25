from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath

from config import Context
from errors import ValidationError
from manifest import resolve_within
from plan import DELETION_KINDS, WRITE_KINDS, SyncPlan
from render import extract_markdown, normalise_source_text


def _destination_path(root: Path, destination: PurePosixPath) -> Path:
    target = resolve_within(
        root,
        root / destination.as_posix(),
        ValidationError,
        f"destination escapes artefacts directory: {destination}",
    )
    current = root
    for component in destination.parts[:-1]:
        current /= component
        if current.is_symlink():
            raise ValidationError(f"destination parent is a symbolic link: {destination}")
    return target


def write_atomic(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, target)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def verify_markdown_round_trip(source_bytes: bytes, rendered: bytes, label: str) -> None:
    try:
        expected = normalise_source_text(source_bytes, label)
        document = rendered.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(f"{label}: markdown round trip is not UTF-8 ({error})") from error
    found = extract_markdown(document)
    if found is None:
        raise ValidationError(f"{label}: rendered page carries no markdown block")
    if found != expected:
        raise ValidationError(f"{label}: markdown did not survive the round trip")


def apply_plan(context: Context, plan: SyncPlan) -> None:
    if plan.blocked:
        raise ValidationError("cannot apply a blocked plan")

    for change in plan.changes:
        if change.kind not in WRITE_KINDS:
            continue
        target = _destination_path(context.artefacts_root, change.destination)
        write_atomic(target, plan.desired_files[change.destination])

    for change in plan.changes:
        if change.kind not in DELETION_KINDS:
            continue
        target = _destination_path(context.artefacts_root, change.destination)
        if target.exists() or target.is_symlink():
            if not target.is_file() or target.is_symlink():
                raise ValidationError(
                    f"refusing to delete non-file destination: {change.destination}"
                )
            target.unlink()
        parent = target.parent
        while parent != context.artefacts_root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    for destination, expected in plan.desired_files.items():
        target = _destination_path(context.artefacts_root, destination)
        if not target.is_file() or target.read_bytes() != expected:
            raise ValidationError(f"applied file differs from plan: {destination}")
    for change in plan.changes:
        if change.kind in DELETION_KINDS and _destination_path(
            context.artefacts_root, change.destination
        ).exists():
            raise ValidationError(f"deleted file remains after apply: {change.destination}")

    if plan.next_manifest is None:
        return
    for entry in plan.next_manifest.entries:
        if entry.source.suffix.lower() != ".md":
            continue
        source = context.source_root / entry.source.as_posix()
        rendered = context.artefacts_root / entry.destination.as_posix()
        if source.is_file() and rendered.is_file():
            verify_markdown_round_trip(
                source.read_bytes(), rendered.read_bytes(), entry.source.as_posix()
            )
