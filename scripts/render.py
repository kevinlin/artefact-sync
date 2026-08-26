from __future__ import annotations

import difflib
import html
import re
import string
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath

from config import ASSETS, Context, Site
from errors import TransformationError
from manifest import TEMPLATE_NAME, VENDOR_NAME, Entry, Manifest, resolve_within

BLOCK_START = '<script type="text/markdown" id="markdown-source">\n'
BLOCK_END = "</script>"
MARKDOWN_MARKER = re.compile(r"<(\\*)(/script|!--)", re.IGNORECASE)
EXISTING_ICON_LINK = re.compile(r"""<link\b[^>]*\brel=["']?[^"'>]*\bicon\b""", re.I)
HEAD_OPEN = re.compile(r"<head\b[^>]*>", re.I)
DOCTYPE = re.compile(r"^\s*<!doctype[^>]*>", re.I)
TRAILING_SPACE = re.compile(r"[ \t]+(?=\r?$)", re.MULTILINE)
# Only assets the browser fetches to render the page count as external loads.
# `href` is an asset on <link> and a plain navigation link everywhere else.
_ASSET_SRC_TAGS = frozenset(
    {"script", "img", "iframe", "embed", "source", "video", "audio", "track", "input"}
)


def normalise_source_text(source_bytes: bytes, label: str) -> str:
    """Decode, normalise line endings, and guarantee a final newline.

    Line endings are normalised because git with `core.autocrlf=input` - a common
    default - stores LF for a CRLF working-tree file, so a page keeping its CRs is
    not the page that gets published, and a fresh clone never converges.
    """
    try:
        text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TransformationError(f"{label}: not valid UTF-8 ({error})") from error
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text and not text.endswith("\n"):
        text += "\n"
    return text


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
    bundled = ASSETS / TEMPLATE_NAME
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
    text = normalise_source_text(source_bytes, entry.source.as_posix())
    prefix = "../" * len(entry.destination.parent.parts)
    document = template.substitute(
        title=html.escape(entry.title),
        favicon=site.favicon,
        prefix=prefix,
        vendor=vendor_path.as_posix(),
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
    text = normalise_source_text(source_bytes, entry.source.as_posix())
    for old, new in entry.replacements.items():
        parts = text.split(old)
        if len(parts) == 1:
            raise TransformationError(f"expected replacement not found for {entry.id}: {old}")
        text = new.join(parts)
    text = TRAILING_SPACE.sub("", text)
    text = ensure_favicon(text, site.favicon)
    return text.encode("utf-8")


class _AssetCollector(HTMLParser):
    """Collect off-site URLs the browser fetches to render the page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attribute = "href" if tag == "link" else "src" if tag in _ASSET_SRC_TAGS else None
        if attribute is None:
            return
        for name, value in attrs:
            if name.lower() != attribute or not value:
                continue
            url = value.strip()
            if not (url.startswith("//") or re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I)):
                continue
            if url.lower().startswith(("data:", "mailto:", "tel:", "#")):
                continue
            self.found.append((self.getpos()[0], url))


def external_references(html_text: str) -> tuple[tuple[int, str], ...]:
    collector = _AssetCollector()
    try:
        collector.feed(html_text)
        collector.close()
    except AssertionError:  # malformed markup: report what was parsed so far
        pass
    return tuple(collector.found)


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
