from __future__ import annotations

import difflib
import html
import re
import string
from pathlib import Path, PurePosixPath

from .config import Context, Site
from .errors import TransformationError
from .manifest import TEMPLATE_NAME, VENDOR_NAME, Entry, Manifest, resolve_within

BLOCK_START = '<script type="text/markdown" id="artefact-source">'
BLOCK_END = "</script>"
MARKDOWN_MARKER = re.compile(r"<(\\*)(/script|!--)", re.IGNORECASE)
EXISTING_ICON_LINK = re.compile(r"""<link\b[^>]*\brel=["']?[^"'>]*\bicon\b""", re.I)
HEAD_OPEN = re.compile(r"<head\b[^>]*>", re.I)
DOCTYPE = re.compile(r"^\s*<!doctype[^>]*>", re.I)
TRAILING_SPACE = re.compile(r"[ \t]+(?=\r?$)", re.MULTILINE)
_REFERENCE = re.compile(r"""\b(?:src|href)\s*=\s*["']([^"']+)["']""", re.I)


def escape_markdown_block(text: str) -> str:
    return MARKDOWN_MARKER.sub(
        lambda match: "<" + "\\" * (len(match.group(1)) + 1) + match.group(2), text
    )


def unescape_markdown_block(text: str) -> str:
    return MARKDOWN_MARKER.sub(
        lambda match: "<" + "\\" * max(len(match.group(1)) - 1, 0) + match.group(2), text
    )


def extract_markdown(document: str) -> str | None:
    start = document.find(BLOCK_START)
    if start < 0:
        return None
    start += len(BLOCK_START)
    end = document.find(BLOCK_END, start)
    if end < 0:
        return None
    return unescape_markdown_block(document[start:end])


def load_template(artefacts_root: Path) -> string.Template:
    override = artefacts_root / TEMPLATE_NAME
    if override.is_file():
        return string.Template(override.read_text(encoding="utf-8"))
    bundled = Path(__file__).resolve().parent / "assets" / TEMPLATE_NAME
    return string.Template(bundled.read_text(encoding="utf-8"))


def markdown_vendor_path(manifest: Manifest) -> PurePosixPath:
    for path in manifest.protected_files:
        if path.name == VENDOR_NAME:
            return path
    raise TransformationError(
        f"{VENDOR_NAME} must be listed in protected_files to publish Markdown; "
        "run 'artefact-sync init' to add it"
    )


def render_markdown_page(
    entry: Entry,
    source_bytes: bytes,
    vendor_path: PurePosixPath,
    site: Site,
    template: string.Template,
) -> bytes:
    try:
        text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TransformationError(f"{entry.source}: not valid UTF-8 ({error})") from error
    if not text.endswith("\n"):
        text += "\n"
    prefix = "../" * len(entry.destination.parent.parts)
    document = template.substitute(
        title=html.escape(entry.title),
        favicon=site.favicon,
        prefix=prefix,
        vendor=prefix + vendor_path.as_posix(),
        markdown=escape_markdown_block(text),
        block_start=BLOCK_START,
        block_end=BLOCK_END,
    )
    return document.encode("utf-8")


def markdown_diff(published: bytes | None, rendered: bytes, limit: int = 40) -> str:
    if published is None:
        return ""
    try:
        previous = extract_markdown(published.decode("utf-8"))
        current = extract_markdown(rendered.decode("utf-8"))
    except UnicodeDecodeError:
        return "diff unavailable: page is not UTF-8"
    if previous is None or current is None:
        return "diff unavailable: page has no embedded Markdown"
    lines = list(
        difflib.unified_diff(
            previous.splitlines(),
            current.splitlines(),
            fromfile="published",
            tofile="source",
            lineterm="",
        )
    )
    if len(lines) > limit:
        remaining = len(lines) - limit
        lines = lines[:limit] + [f"... truncated, {remaining} more lines"]
    return "\n".join(lines)


def ensure_favicon(text: str, favicon: str) -> str:
    if EXISTING_ICON_LINK.search(text):
        return text
    head = HEAD_OPEN.search(text)
    if head is not None:
        return f"{text[: head.end()]}\n    {favicon}{text[head.end() :]}"
    doctype = DOCTYPE.match(text)
    prefix = f"{text[: doctype.end()]}\n" if doctype else ""
    rest = text[doctype.end() :] if doctype else text
    return f"{prefix}{favicon}\n{rest.lstrip()}"


def transform_html(source_bytes: bytes, entry: Entry, site: Site) -> bytes:
    try:
        text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TransformationError(f"{entry.source}: not valid UTF-8 ({error})") from error
    for old, new in entry.replacements.items():
        parts = text.split(old)
        if len(parts) == 1:
            raise TransformationError(f"expected replacement not found for {entry.id}: {old}")
        text = new.join(parts)
    text = TRAILING_SPACE.sub("", text)
    text = ensure_favicon(text, site.favicon)
    if text and not text.endswith(("\n", "\r")):
        text += "\n"
    return text.encode("utf-8")


def external_references(html_text: str) -> tuple[tuple[int, str], ...]:
    found = []
    for number, line in enumerate(html_text.splitlines(), start=1):
        for match in _REFERENCE.finditer(line):
            url = match.group(1).strip()
            if url.startswith("//") or re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I):
                if not url.lower().startswith(("data:", "mailto:", "tel:", "#")):
                    found.append((number, url))
    return tuple(found)


def build_desired_files(
    context: Context, manifest: Manifest, template: string.Template
) -> dict[PurePosixPath, bytes]:
    root = context.source_root.resolve()
    desired: dict[PurePosixPath, bytes] = {}
    for entry in manifest.entries:
        source_path = context.source_root / entry.source.as_posix()
        if not source_path.exists():
            continue
        if source_path.is_symlink():
            raise TransformationError(f"symbolic link is not allowed: {source_path}")
        resolve_within(
            root,
            source_path,
            TransformationError,
            f"source path escapes source directory: {source_path}",
        )
        source_bytes = source_path.read_bytes()
        suffix = entry.source.suffix.lower()
        if suffix == ".html":
            output = transform_html(source_bytes, entry, context.site)
        elif suffix == ".md":
            output = render_markdown_page(
                entry,
                source_bytes,
                markdown_vendor_path(manifest),
                context.site,
                template,
            )
        else:
            output = source_bytes
        desired[entry.destination] = output
    return desired
