from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from . import apply as apply_module
from . import catalogue, config, manifest, plan as plan_module, render, scan
from .errors import ArtefactSyncError, ConfigError, UnlistedSources, ValidationError

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BLOCKED = 3
SEED_IGNORES = ("prompts/", "drafts/", "*.local.*", ".*")
_GITHUB = re.compile(r"(?:git@github\.com:|https://github\.com/)([^/]+)/(.+?)(?:\.git)?/?$")


def _add_context_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pointer", type=Path, default=config.POINTER_PATH,
                        help=argparse.SUPPRESS)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--source", type=Path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="artefact-sync")
    sub = parser.add_subparsers(dest="command")
    for name in ("init", "plan", "sync", "publish", "validate"):
        child = sub.add_parser(name)
        _add_context_args(child)
        if name == "sync":
            child.add_argument("--yes", action="store_true")
    add = sub.add_parser("add")
    add.add_argument("path", type=Path)
    _add_context_args(add)
    return parser.parse_args(argv)


def resolve_context(args: argparse.Namespace) -> config.Context:
    pointer = config.load_pointer(args.pointer)
    if args.repo:
        pointer = config.Pointer(args.repo, pointer.source, pointer.push)
    if args.source:
        pointer = config.Pointer(pointer.repo, args.source, pointer.push)
    site = manifest.load_manifest(pointer.repo / config.ARTEFACTS_DIRNAME).site
    return config.build_context(pointer, site)


def derive_base_url(repo_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    match = _GITHUB.search(result.stdout.strip())
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    if repo.lower() == f"{owner.lower()}.github.io":
        return f"https://{owner}.github.io/"
    return f"https://{owner}.github.io/{repo}/"


def command_init(args: argparse.Namespace) -> int:
    repo_root = (args.repo or Path.cwd()).expanduser().resolve()
    if not repo_root.is_dir():
        raise ConfigError(f"repository directory does not exist: {repo_root}")
    source_root = (args.source or Path.home() / "Downloads" / "Artefacts").expanduser().resolve()
    source_root.mkdir(parents=True, exist_ok=True)
    config.save_pointer(config.Pointer(repo_root, source_root, "direct"), args.pointer)

    artefacts = repo_root / config.ARTEFACTS_DIRNAME
    (artefacts / "vendor").mkdir(parents=True, exist_ok=True)
    assets = Path(__file__).resolve().parent / "assets"
    for name, target in (
        (manifest.TEMPLATE_NAME, artefacts / manifest.TEMPLATE_NAME),
        (manifest.VENDOR_NAME, artefacts / "vendor" / manifest.VENDOR_NAME),
    ):
        if not target.is_file():
            shutil.copyfile(assets / name, target)

    guessed_url = derive_base_url(repo_root)
    manifest_path = artefacts / manifest.MANIFEST_NAME
    if not manifest_path.is_file():
        seeded = manifest.Manifest(
            version=1,
            site=config.site_from_dict(
                {"base_url": guessed_url or "https://example.invalid/artefacts/"}
            ),
            protected_files=(PurePosixPath("vendor") / manifest.VENDOR_NAME,),
            ignored_sources=SEED_IGNORES,
            collections=(),
            entries=(),
        )
        manifest_path.write_text(manifest.manifest_to_json(seeded), encoding="utf-8")

    loaded = manifest.load_manifest(artefacts)
    catalogue_path = artefacts / manifest.CATALOGUE_NAME
    if not catalogue_path.is_file():
        catalogue_path.write_bytes(catalogue.render_standalone_catalogue(loaded, loaded.site))
    print(f"pointer written to {args.pointer}")
    print(f"seeded {artefacts}")
    if guessed_url is None:
        print("could not derive a Pages URL from origin; set site.base_url in the manifest")
    return EXIT_OK


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
            notes.append(plan_module.Note("external", f"artefacts/{relative}:{line}", url))
        for reference in _parse_references(text).references:
            target = _local_reference(context, path, reference)
            if target is not None and not target.is_file():
                raise ValidationError(f"broken local reference in {relative}: {reference}")
    return tuple(notes)


def _command_state(
    args: argparse.Namespace,
) -> tuple[config.Context, manifest.Manifest]:
    context = resolve_context(args)
    current = manifest.load_manifest(context.artefacts_root)
    manifest.check_published_invariants(current, manifest.head_manifest(context.repo_root))
    return context, current


def _write_proposed_manifest(context: config.Context, sync_plan: plan_module.SyncPlan) -> bool:
    if sync_plan.next_manifest is None or not any(
        item.detail.startswith("approved source has no manifest entry")
        for item in sync_plan.blocked
    ):
        return False
    body = manifest.manifest_to_json(sync_plan.next_manifest).encode("utf-8")
    apply_module.write_atomic(context.artefacts_root / manifest.MANIFEST_NAME, body)
    return True


def command_plan(args: argparse.Namespace) -> int:
    context, current = _command_state(args)
    sync_plan = plan_module.create_sync_plan(context, current)
    print(plan_module.format_plan(sync_plan), end="")
    if sync_plan.blocked:
        _write_proposed_manifest(context, sync_plan)
        return EXIT_BLOCKED
    return EXIT_OK


def command_sync(args: argparse.Namespace) -> int:
    context, current = _command_state(args)
    sync_plan = plan_module.create_sync_plan(context, current)
    print(plan_module.format_plan(sync_plan), end="")
    if sync_plan.blocked:
        _write_proposed_manifest(context, sync_plan)
        return EXIT_BLOCKED
    if not args.yes and input("Apply these changes? Type yes to continue: ") != "yes":
        print("sync cancelled; nothing was applied.")
        return EXIT_ERROR
    apply_module.apply_plan(context, sync_plan)
    return EXIT_OK


def command_validate(args: argparse.Namespace) -> int:
    context, current = _command_state(args)
    for note in validate_repository(context, current):
        print(f"warning: {note.kind} {note.where}: {note.detail}")
    return EXIT_OK


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "init":
        return command_init(args)
    commands = {
        "plan": command_plan,
        "sync": command_sync,
        "validate": command_validate,
    }
    command = commands.get(args.command)
    if command is None:
        raise ConfigError(f"{args.command} command is not available in M1")
    return command(args)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.command:
        print("usage: artefact-sync {init,plan,sync,add,publish,validate}", file=sys.stderr)
        return EXIT_ERROR
    try:
        return _dispatch(args)
    except UnlistedSources as blocked:
        print(str(blocked), file=sys.stderr)
        return EXIT_BLOCKED
    except ArtefactSyncError as error:
        print(str(error), file=sys.stderr)
        return EXIT_ERROR
